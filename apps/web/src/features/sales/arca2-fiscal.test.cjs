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
  useEffect(fn, deps) { const h = current, i = h.index++; if (!h.values[i] || deps.some((value, j) => !Object.is(value, h.values[i].deps[j]))) { h.values[i]?.cleanup?.(); h.values[i] = { deps }; h.pending.push(() => { h.values[i].cleanup = fn(); }); } },
};
const load = Module._load;
Module._load = function (name, ...args) { if (name === "react") return hooks; return load.call(this, name, ...args); };
const { SaleFiscalEmissionPanel } = require("./components/sale-fiscal-emission-panel.tsx");
const { FiscalEmissionReadinessPanel } = require("./components/fiscal-emission-readiness-panel.tsx");
Module._load = load;
const { initialEmissionForm, buildEmissionPayload, emissionLineTotal, emissionLinesTotal } = require("./components/arca-emission-helpers.ts");
const { getFiscalEmissionFile } = require("../../services/arca-emission.ts");
const { setAuthTokenProvider, setActingTenantId } = require("../../lib/api.ts");
const flush = async () => { for (let i = 0; i < 150; i++) await Promise.resolve(); };
function nodes(tree) { if (Array.isArray(tree)) return tree.flatMap(nodes); if (!tree || typeof tree !== "object") return []; return [tree, ...nodes(tree.props?.children)]; }
function content(tree) { if (Array.isArray(tree)) return tree.map(content).join(""); if (tree && typeof tree === "object") return content(tree.props?.children); return typeof tree === "string" || typeof tree === "number" ? String(tree) : ""; }

const issuer = { cuit: "20123456786", legal_name: "Profesional sintético", tax_condition: "Monotributo", fiscal_address: "Domicilio sintético", gross_income_registration: "Inscripción sintética", activity_start_date: "2020-01-01", fiscal_data_review_note: null };
const business = { environment: "homologation", issuer, receiver: { document_type: 99, document_number: 0, iva_condition_id: 5, name: "Receptor sintético", address: "Dirección de prueba", consumer_final: true }, point_of_sale: 7, document_type: 15, concept: 2, voucher_date: "2026-10-20", service_from: "2026-10-20", service_to: "2026-10-20", payment_due: "2026-10-20", currency: "PES", exchange_rate: "1", total: "10.10", net_amount: "10.10", lines: [{ description: "Porción confirmada", quantity: "1", unit_price: "10.10", total: "10.10" }] };
const proposal = { id: "proposal-a", fiscal_issuer_id: "issuer-a", status: "approved", currency: "ARS", total_ars: "10.10", concept: 2, fiscal_description: "Porción confirmada", snapshot: { issuer, series: { point_of_sale: 7, environment: "homologation", document_type: "receipt_c" } } };
const operation = { id: "emission-a", proposal_id: proposal.id, sale_id: "sale-a", status: "prepared", environment: "homologation", request_hash: "a".repeat(64), business_snapshot: business, number: null, cae: null, cae_expiry: null, document_id: null, file_status: "pending", diagnostics: [], next_action_at: null, attempts: [], file_versions: [], allowed_actions: { issue: true, reconcile: false, regenerate: false, download: false } };
const permissions = { can_prepare: true, can_issue: true, can_reconcile: true, can_regenerate: true, own_issuer_id: null };
const credentialReadiness = { credential: { status: "not_provisioned", diagnostic: "Referencia sin material provisionado" }, remote_validation: "pending", parameters: null, blockers: [{ code: "credential_missing", message: "Provisiona credenciales de homologación fuera del repositorio" }], production_blocked: true };

function setup(t, options = {}) {
  const oldFetch = global.fetch;
  const h = { values: [], pending: [], requests: [], updates: 0, sale: { id: "sale-a" }, emissions: structuredClone({ operations: [], permissions, external_validation: "pending", production_blocked: true, ...options.emissions }), proposals: structuredClone(options.proposals ?? [proposal]), readiness: structuredClone(options.readiness ?? credentialReadiness) };
  setAuthTokenProvider(async () => "synthetic-token"); setActingTenantId(null);
  const response = (data, status = 200) => new Response(JSON.stringify(status === 200 ? { data, meta: {} } : { error: { code: "fiscal_blocked", message: data } }), { status, headers: { "Content-Type": "application/json" } });
  global.fetch = async (url, init) => {
    const request = { url: new URL(url), init, body: init.body ? JSON.parse(init.body) : null }; h.requests.push(request);
    assert.equal(init.headers.get("Authorization"), "Bearer synthetic-token"); assert.equal(init.headers.has("X-Tenant-Id"), false);
    if (options.respond) { const result = options.respond(request, h, response); if (result) return result; }
    if (init.method === "GET") return response(request.url.pathname.endsWith("fiscal-review") ? { proposals: h.proposals } : request.url.pathname.endsWith("emission-readiness") ? h.readiness : h.emissions);
    if (request.url.pathname.endsWith("/fiscal-emissions")) { h.emissions.operations.push({ ...operation, business_snapshot: request.body.fiscal_data }); return response(h.emissions.operations.at(-1)); }
    if (request.url.pathname.endsWith("/reconcile")) { h.emissions.operations = h.emissions.operations.map(op => ({ ...op, status: "authorized", number: 42, cae: "70417054367476", cae_expiry: "2026-10-30", allowed_actions: { ...op.allowed_actions, reconcile: false, issue: false, regenerate: true } })); }
    if (request.url.pathname.endsWith("/regenerate")) { h.emissions.operations = h.emissions.operations.map(op => ({ ...op, file_status: "ready", file_versions: [{ id: "version-a", sha256: "b".repeat(64), created_at: "2026-10-20" }], allowed_actions: { ...op.allowed_actions, download: true } })); }
    return response(h.emissions.operations[0]);
  };
  const configuration = { series: [{ id: "series-a", cuit_snapshot: issuer.cuit, environment: "homologation", point_of_sale: 7, document_type: "receipt_c" }] };
  h.render = () => { current = h; h.index = 0; h.tree = options.settings ? FiscalEmissionReadinessPanel({ configuration }) : SaleFiscalEmissionPanel({ sale: h.sale, onUpdated: async () => { h.updates++; } }); h.pending.splice(0).forEach(fn => fn()); return h.tree; };
  h.ready = async () => { h.render(); await flush(); h.render(); };
  h.find = predicate => { const node = nodes(h.tree).find(predicate); assert.ok(node, "Expected element"); return node; };
  h.button = text => h.find(n => n.type === "button" && content(n).trim() === text);
  h.click = text => { const b = h.button(text); assert.ok(!b.props.disabled); const result = b.props.onClick(); h.render(); return result; };
  h.input = (id, value) => { h.find(n => n.props?.id === id).props.onChange({ target: { value } }); h.render(); };
  h.check = text => { const label = h.find(n => n.type === "label" && content(n).includes(text)); const input = nodes(label).find(n => n.type === "input" && n.props.type === "checkbox"); assert.ok(input && !input.props.disabled); input.props.onChange({ target: { checked: true } }); h.render(); };
  h.submit = () => { const result = h.find(n => n.type === "form").props.onSubmit({ preventDefault() {} }); h.render(); return result; };
  h.writes = () => h.requests.filter(r => r.init.method !== "GET");
  t.after(() => { h.values.forEach(value => value?.cleanup?.()); global.fetch = oldFetch; setAuthTokenProvider(null); });
  return h;
}

function completeForm(h, button = "Completar intención fiscal") {
  h.click(button);
  h.input("emission-fiscal-address", "Domicilio fiscal sintético"); h.input("emission-issuer-note", "Revisión sintética: datos no aplicables confirmados");
  h.input("emission-receiver-name", "Receptor confirmado"); h.input("emission-receiver-address", "Domicilio receptor sintético");
  h.input("emission-consumer-final", "yes"); h.check("Confirmo que corresponde receptor sin identificar");
  for (const id of ["emission-voucher-date", "emission-service-from", "emission-service-to", "emission-payment-due"]) h.input(id, "2026-10-20");
  h.check("Confirmo identidad, receptor, fechas y detalle");
}

test("line representation closes in cents including half-up rounding without floats", () => {
  assert.equal(emissionLineTotal("0.05", "0.10"), "0.01"); assert.equal(emissionLineTotal("3", "0.10"), "0.30");
  assert.equal(emissionLinesTotal([{ total: "999999999999.99" }, { total: "0.01" }]), "1000000000000.00");
  assert.throws(() => emissionLineTotal("NaN", "1.00"));
});

test("intent cannot infer receiver identity or fiscal obligations from owner free text", async t => {
  const initial = initialEmissionForm(proposal); assert.equal(initial.consumer_final, ""); assert.equal(initial.document_type, ""); assert.equal(initial.document_number, ""); assert.equal(initial.iva_condition_id, ""); assert.equal(initial.voucher_date, "");
  const h = setup(t); await h.ready(); h.click("Completar intención fiscal"); assert.equal(h.button("Guardar intención sin enviar").props.disabled, true); assert.equal(h.writes().length, 0);
  h.input("emission-consumer-final", "yes"); assert.equal(h.find(n => n.props?.id === "emission-vat-condition").props.value, "5"); assert.equal(h.find(n => n.props?.id === "emission-doc-type").props.value, "");
  h.check("Confirmo que corresponde receptor sin identificar"); assert.equal(h.find(n => n.props?.id === "emission-doc-number").props.value, "0"); h.input("emission-consumer-final", "no"); assert.equal(h.find(n => n.props?.id === "emission-doc-type").props.value, "");
});

test("prepare persists exact documented portion under idempotency identity without issuing", async t => {
  const h = setup(t); await h.ready(); completeForm(h); await h.submit(); await flush(); h.render();
  assert.equal(h.writes().length, 1); const request = h.writes()[0]; assert.equal(request.url.pathname, "/api/v1/sales/sale-a/fiscal-emissions"); assert.equal(request.body.proposal_id, proposal.id); assert.equal(request.body.confirm_fiscal_identity, true); assert.ok(request.init.headers.get("Idempotency-Key"));
  assert.equal(request.body.fiscal_data.total, "10.10"); assert.deepEqual(request.body.fiscal_data.lines, business.lines); assert.equal(request.body.fiscal_data.receiver.consumer_final, true); assert.equal("tenant_id" in request.body, false); assert.equal("number" in request.body.fiscal_data, false); assert.match(content(h.tree), /Intención fiscal guardada sin enviar/); assert.equal(h.updates, 1);
});

test("prepare retries unchanged data with same key and preserves form after refusal", async t => {
  let fail = true;
  const h = setup(t, { respond(r, h, response) { if (r.init.method === "POST" && fail) return response("Credencial pendiente", 409); } }); await h.ready(); completeForm(h); await h.submit(); await flush(); h.render(); assert.match(content(h.tree), /Credencial pendiente/); fail = false; await h.submit(); await flush(); h.render();
  assert.equal(h.writes().length, 2); assert.equal(h.writes()[0].init.headers.get("Idempotency-Key"), h.writes()[1].init.headers.get("Idempotency-Key")); assert.deepEqual(h.writes()[0].body, h.writes()[1].body);
});

test("duplicate synchronous prepare is blocked", async t => {
  let finish;
  const h = setup(t, { respond(r, h, response) { if (r.init.method === "POST") return new Promise(resolve => { finish = () => resolve(response(operation)); }); } }); await h.ready(); completeForm(h); const submit = h.find(n => n.type === "form").props.onSubmit; submit({ preventDefault() {} }); submit({ preventDefault() {} }); await flush(); assert.equal(h.writes().length, 1); finish(); await flush(); h.render();
});

test("issue requires explicit confirmation and always uses the persisted intent ID", async t => {
  const h = setup(t, { emissions: { operations: [operation] } }); await h.ready(); assert.equal(h.button("Solicitar CAE de esta intención").props.disabled, true); h.check("Confirmo enviar esta intención"); await h.click("Solicitar CAE de esta intención"); await flush(); h.render();
  assert.deepEqual(h.writes().map(r => [r.url.pathname, r.body]), [["/api/v1/sales/sale-a/fiscal-emissions/emission-a/issue", { confirm: true }]]);
});

test("lost HTTP response recovers durable unknown state without automatically reissuing", async t => {
  const h = setup(t, { emissions: { operations: [operation] }, respond(r, h) { if (r.url.pathname.endsWith("/issue")) { h.emissions.operations[0] = { ...h.emissions.operations[0], status: "unknown", number: 42, allowed_actions: { issue: false, reconcile: true, regenerate: false, download: false } }; throw new TypeError("Synthetic interrupted response"); } } }); await h.ready(); h.check("Confirmo enviar esta intención"); await h.click("Solicitar CAE de esta intención"); await flush(); h.render(); assert.equal(h.writes().length, 1); assert.match(content(h.tree), /Resultado incierto/); assert.equal(nodes(h.tree).some(n => n.type === "button" && content(n).includes("Solicitar CAE")), false); h.button("Reconciliar resultado existente"); assert.equal(h.updates, 1);
});

test("unknown intent reconciles same number and never exposes cancellation or another issue", async t => {
  const h = setup(t, { emissions: { operations: [{ ...operation, status: "unknown", number: 42, allowed_actions: { issue: true, reconcile: true, regenerate: false, download: false } }] } }); await h.ready(); assert.match(content(h.tree), /No canceles ni prepares otra emisión/); assert.equal(nodes(h.tree).some(n => n.type === "button" && /Solicitar CAE|Completar intención|Cancelar/.test(content(n))), false);
  await h.click("Reconciliar resultado existente"); await flush(); h.render(); assert.deepEqual(h.writes().map(r => [r.url.pathname, r.body]), [["/api/v1/sales/sale-a/fiscal-emissions/emission-a/reconcile", {}]]); assert.match(content(h.tree), /CAE 70417054367476/);
});

test("authorized file failure regenerates artifact without another authorization", async t => {
  const h = setup(t, { emissions: { operations: [{ ...operation, status: "authorized", number: 42, cae: "70417054367476", cae_expiry: "2026-10-30", file_status: "failed", allowed_actions: { issue: false, reconcile: false, regenerate: true, download: false } }] } }); await h.ready(); assert.match(content(h.tree), /Autorizado, archivo pendiente/); await h.click("Regenerar PDF y QR"); await flush(); h.render(); assert.equal(h.writes()[0].url.pathname, "/api/v1/sales/sale-a/fiscal-emissions/emission-a/regenerate"); assert.equal(h.writes().length, 1); h.button("Descargar comprobante"); h.button("Descargar versión version-a"); assert.match(content(h.tree), /SHA256/);
});

test("definitive rejection keeps audit and permits completing a new reviewed intention", async t => {
  const h = setup(t, { emissions: { operations: [{ ...operation, status: "rejected", allowed_actions: { issue: false, reconcile: false, regenerate: false, download: false }, diagnostics: [{ code: "100", message: "Receptor requiere corrección" }] }] } }); await h.ready(); assert.match(content(h.tree), /Rechazo definitivo/); assert.match(content(h.tree), /nueva y auditada/); h.button("Preparar corrección de esta intención rechazada"); assert.equal(nodes(h.tree).some(n => n.type === "button" && content(n).includes("Solicitar CAE")), false);
  completeForm(h, "Preparar corrección de esta intención rechazada"); await h.submit(); await flush(); h.render(); assert.equal(h.writes()[0].body.supersedes_id, operation.id);
});

test("secretary is read-only and veterinarian preparation excludes other issuers", async t => {
  const h = setup(t, { emissions: { permissions: { ...permissions, can_prepare: false, can_issue: false, can_reconcile: false, can_regenerate: false }, operations: [operation] } }); await h.ready(); assert.match(content(h.tree), /Consulta de operaciones/); assert.equal(nodes(h.tree).some(n => n.type === "button" && /Solicitar CAE|Completar intención|Regenerar/.test(content(n))), false);
});

test("veterinarian cannot prepare a proposal linked to another issuer", async t => {
  const h = setup(t, { emissions: { permissions: { ...permissions, own_issuer_id: "another-issuer" } } }); await h.ready(); assert.equal(nodes(h.tree).some(n => n.type === "button" && content(n) === "Completar intención fiscal"), false);
});

test("production and mismatched detail fail before preparing or connecting", () => {
  const form = { ...initialEmissionForm(proposal), fiscal_address: "Sintético", fiscal_data_review_note: "Revisado", receiver_name: "Receptor", receiver_address: "Dirección", consumer_final: "yes", document_type: "99", document_number: "0", iva_condition_id: "5", voucher_date: "2026-10-20", service_from: "2026-10-20", service_to: "2026-10-20", payment_due: "2026-10-20" };
  assert.throws(() => buildEmissionPayload({ ...proposal, snapshot: { ...proposal.snapshot, series: { ...proposal.snapshot.series, environment: "production" } } }, form), /producción/);
  assert.throws(() => buildEmissionPayload(proposal, { ...form, lines: [{ ...form.lines[0], unit_price: "10.00", total: "10.00" }] }), /exactamente/);
});

test("credential readiness uses local metadata only after explicit selection, with no fake parameters", async t => {
  const h = setup(t, { settings: true }); await h.ready(); assert.equal(h.requests.length, 0); assert.equal(h.button("Consultar preparación de homologación").props.disabled, true); h.input("readiness-series", "series-a"); await h.click("Consultar preparación de homologación"); await flush(); h.render(); assert.equal(h.requests.length, 1); assert.equal(h.requests[0].url.pathname, "/api/v1/fiscal/emission-readiness"); assert.equal(h.requests[0].url.searchParams.get("series_id"), "series-a"); assert.match(content(h.tree), /Credencial pendiente de provisión/); assert.match(content(h.tree), /Validación remota pendiente/); assert.match(content(h.tree), /Sin parámetros remotos disponibles/); assert.equal(h.writes().length, 0);
});

test("version download keeps authenticated emission identity and opaque version query", async t => {
  const h = setup(t, { respond(r) { if (r.url.pathname.endsWith("/file")) return new Response("%PDF-synthetic", { headers: { "Content-Type": "application/pdf" } }); } }); await getFiscalEmissionFile("sale-a", "emission-a", "version-a"); assert.equal(h.requests[0].url.pathname, "/api/v1/sales/sale-a/fiscal-emissions/emission-a/file"); assert.equal(h.requests[0].url.searchParams.get("version_id"), "version-a");
});

test("uncertain recovery resends only after separate explicit confirmation using the same persisted operation", async t => {
  const h = setup(t, { emissions: { operations: [{ ...operation, status: "unknown", number: 42, allowed_actions: { issue: false, reconcile: true, regenerate: false, download: false, retry_same_request: true } }] } }); await h.ready(); assert.equal(h.button("Reenviar exactamente la solicitud y número persistidos").props.disabled, true);
  h.check("Confirmo conservar exactamente el número y la solicitud persistidos"); await h.click("Reenviar exactamente la solicitud y número persistidos"); await flush(); h.render();
  assert.deepEqual(h.writes().map(r => [r.url.pathname, r.body]), [["/api/v1/sales/sale-a/fiscal-emissions/emission-a/reconcile", { retry_same_request: true, confirm: true }]]);
});

test("editing reviewed fiscal data requires confirming the new content again", async t => {
  const h = setup(t); await h.ready(); completeForm(h); assert.equal(h.button("Guardar intención sin enviar").props.disabled, false); h.input("emission-receiver-address", "Otro domicilio confirmado"); assert.equal(h.button("Guardar intención sin enviar").props.disabled, true); assert.equal(h.writes().length, 0);
});

test("readiness cannot validate remotely without explicit server action permission", async t => {
  const h = setup(t, { settings: true }); await h.ready(); h.input("readiness-series", "series-a"); await h.click("Consultar preparación de homologación"); await flush(); h.render();
  assert.equal(h.button("Validar acceso y parámetros remotos de homologación").props.disabled, true);
  assert.equal(h.find(n => n.type === "fieldset").props.disabled, true);
  assert.equal(h.writes().length, 0);
});

test("remote readiness validation needs a separate confirmation and posts once without retries", async t => {
  const h = setup(t, { settings: true, readiness: { ...credentialReadiness, credential: { status: "configured", diagnostic: null, expires_at: "2026-10-20T13:00:00Z" }, allowed_actions: { validate: true } }, respond(r, h, response) { if (r.url.pathname.endsWith("/validate")) return response("Acceso de homologación todavía pendiente", 503); } });
  await h.ready(); h.input("readiness-series", "series-a"); await h.click("Consultar preparación de homologación"); await flush(); h.render();
  assert.match(content(h.tree), /Referencia configurada; material pendiente de validación/); assert.match(content(h.tree), /Vencimiento del ticket/);
  assert.equal(h.button("Validar acceso y parámetros remotos de homologación").props.disabled, true); assert.equal(h.writes().length, 0);
  h.check("Confirmo consultar WSAA y parámetros de homologación"); await h.click("Validar acceso y parámetros remotos de homologación"); await flush(); h.render();
  assert.deepEqual(h.writes().map(r => [r.init.method, r.url.pathname, r.body]), [["POST", "/api/v1/fiscal/emission-readiness/validate", { series_id: "series-a" }]]);
  assert.match(content(h.tree), /Intenta nuevamente/); assert.equal(h.button("Validar acceso y parámetros remotos de homologación").props.disabled, true);
});

test("explicit readiness validation displays returned catalogs instead of invented defaults", async t => {
  const h = setup(t, { settings: true, readiness: { ...credentialReadiness, allowed_actions: { validate: true } }, respond(r, h, response) { if (r.url.pathname.endsWith("/validate")) return response({ ...h.readiness, remote_validation: "validated", parameters: { FEParamGetPtosVenta: [{ Nro: "7", Tipo: "Web Services consultado" }] }, blockers: [] }); } });
  await h.ready(); h.input("readiness-series", "series-a"); await h.click("Consultar preparación de homologación"); await flush(); h.render(); h.check("Confirmo consultar WSAA y parámetros de homologación"); await h.click("Validar acceso y parámetros remotos de homologación"); await flush(); h.render();
  assert.match(content(h.tree), /Puntos de venta/); assert.match(content(h.tree), /7 · Web Services consultado/); assert.match(content(h.tree), /Parámetros remotos consultados/); assert.equal(h.writes().length, 1);
});
