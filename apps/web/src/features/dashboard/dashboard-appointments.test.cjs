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

const { buildDashboardAppointmentFilters, selectDashboardAppointments } = require("./components/dashboard-appointments.ts");
const { DashboardAppointmentsCard } = require("./components/dashboard-appointments-card.tsx");
const { getAppointments } = require("../../services/appointments.ts");
const { setAuthTokenProvider, setActingTenantId } = require("../../lib/api.ts");

const appointment = (id, start_at, status = "scheduled") => ({
  id, start_at, end_at: start_at, status, title: `Consulta ${id}`,
  appointment_type: "consultation", patient_name: "Luna", owner_name: "María Pérez",
});
const render = (appointments, now) => renderToStaticMarkup(React.createElement(DashboardAppointmentsCard, { appointments, now }));
function inTimezone(zone, callback) {
  const previous = process.env.TZ;
  process.env.TZ = zone;
  try { callback(); } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
}

test("today uses Agenda's local day across UTC midnight; tomorrow never appears in Hoy", () => {
  inTimezone("America/Panama", () => {
    const now = new Date("2026-09-20T23:30:00-05:00");
    const items = [
      appointment("tomorrow", "2026-09-21T05:00:00Z"),
      appointment("today", "2026-09-21T04:59:59Z"),
      appointment("previous", "2026-09-20T04:59:59Z"),
    ];
    const result = selectDashboardAppointments(items, now);
    assert.deepEqual(result.today.map(item => item.id), ["today"]);
    assert.equal(result.next.id, "tomorrow");
    const html = render(items, now);
    assert.ok(html.includes("Consulta today"));
    assert.ok(!html.includes("Consulta tomorrow"));
    assert.ok(!html.includes("Consulta previous"));
    assert.ok(html.includes('href="/agenda"'));
    assert.ok(html.includes("Ver agenda"));
    assert.ok(html.includes('href="/agenda/today"'));
    assert.ok(html.includes("<h2>Turnos</h2>"));
  });
});

test("scheduled appointments today are sorted and limited to four without mutating input", () => {
  const now = new Date(2026, 8, 20, 8);
  const items = [13, 11, 9, 12, 10].map(hour => appointment(String(hour), new Date(2026, 8, 20, hour).toISOString()));
  const result = selectDashboardAppointments([
    ...items,
    ...["completed", "cancelled", "no_show"].map(status => appointment(status, new Date(2026, 8, 20, 7).toISOString(), status)),
  ], now);
  assert.deepEqual(result.today.map(item => item.id), ["9", "10", "11", "12"]);
  assert.deepEqual(items.map(item => item.id), ["13", "11", "9", "12", "10"]);
  const html = render(items, now);
  assert.ok(html.indexOf("Consulta 9") < html.indexOf("Consulta 10"));
  assert.ok(!html.includes("Consulta 13"));
});

test("empty today shows only the nearest future appointment with an explicit tomorrow label", () => {
  inTimezone("America/Panama", () => {
    const now = new Date("2026-09-20T10:00:00-05:00");
    const html = render([
      appointment("later", "2026-09-23T10:00:00-05:00"),
      appointment("next", "2026-09-21T09:30:00-05:00"),
      appointment("cancelled", "2026-09-21T08:00:00-05:00", "cancelled"),
    ], now);
    assert.ok(html.includes("No hay turnos programados para hoy."));
    assert.ok(html.includes("Mañana · 09:30"));
    assert.ok(html.includes("Luna · María Pérez"));
    assert.ok(!html.includes("Consulta later"));
    assert.ok(!html.includes("Consulta cancelled"));
    assert.ok(html.indexOf("Próximo turno") < html.indexOf("Consulta next"));
  });
});

test("appointments beyond 24 hours and across years have an explicit date", () => {
  const now = new Date(2026, 11, 30, 10);
  const html = render([appointment("next-year", new Date(2027, 0, 4, 9, 30).toISOString())], now);
  assert.ok(html.includes("Consulta next-year"));
  assert.ok(html.includes("2027"));
  assert.ok(!html.includes("Mañana"));
});

test("empty and historical or terminal-only data render the empty state without history", () => {
  const now = new Date(2026, 8, 20, 10);
  for (const items of [[], [
    appointment("past", new Date(2026, 8, 19, 10).toISOString()),
    appointment("completed", new Date(2026, 8, 20, 9).toISOString(), "completed"),
    appointment("cancelled", new Date(2026, 8, 21, 9).toISOString(), "cancelled"),
  ]]) {
    const html = render(items, now);
    assert.ok(html.includes("No hay turnos programados para hoy ni próximos."));
    assert.ok(!html.includes("Próximo turno"));
    assert.ok(!html.includes("Consulta "));
    assert.equal((html.match(/class="panel /g) || []).length, 1);
    assert.ok(!html.includes('class="dashboard-row"'));
    assert.ok(html.includes('href="/agenda"'));
  }
});

test("local day boundaries and tomorrow labels hold through DST and month changes", () => {
  for (const [zone, day] of [["America/New_York", "2026-03-08"], ["America/New_York", "2026-11-01"], ["Asia/Tokyo", "2026-12-31"]]) {
    inTimezone(zone, () => {
      const now = new Date(`${day}T12:00:00`);
      const midnight = new Date(`${day}T00:00:00`);
      const tomorrow = new Date(midnight);
      tomorrow.setDate(tomorrow.getDate() + 1);
      const lastMinute = new Date(tomorrow.getTime() - 1);
      const items = [appointment("start", midnight.toISOString()), appointment("end", lastMinute.toISOString()), appointment("next", tomorrow.toISOString())];
      const selected = selectDashboardAppointments(items, now);
      assert.deepEqual(selected.today.map(item => item.id), ["start", "end"]);
      assert.equal(selected.next.id, "next");
      assert.equal(buildDashboardAppointmentFilters("all", now).date_from, midnight.toISOString());
      assert.ok(render([items[2]], now).includes("Mañana ·"));
    });
  }
});

test("query uses authenticated Agenda API, local midnight, scheduled status and veterinarian without a future cutoff", async () => {
  const now = new Date("2026-09-20T15:00:00Z");
  let filters;
  inTimezone("America/Panama", () => {
    filters = buildDashboardAppointmentFilters("vet-a", now);
    assert.equal(filters.date_from, "2026-09-20T05:00:00.000Z");
    assert.equal(buildDashboardAppointmentFilters("all", now).assigned_user_id, undefined);
  });
  const previousFetch = global.fetch;
  setAuthTokenProvider(async () => "test-token");
  setActingTenantId(null);
  global.fetch = async (url, init) => {
    const parsed = new URL(url);
    assert.equal(parsed.pathname, "/api/v1/appointments");
    assert.equal(parsed.searchParams.get("date_from"), filters.date_from);
    assert.equal(parsed.searchParams.get("status"), "scheduled");
    assert.equal(parsed.searchParams.get("assigned_user_id"), "vet-a");
    assert.equal(parsed.searchParams.has("date_to"), false);
    assert.equal(parsed.searchParams.has("tenant_id"), false);
    assert.equal(init.headers.get("Authorization"), "Bearer test-token");
    assert.equal(init.headers.has("X-Tenant-Id"), false);
    assert.equal(init.headers.has("X-Acting-Tenant-Id"), false);
    return new Response(JSON.stringify({ data: [], meta: {} }), { status: 200 });
  };
  try { await getAppointments(filters); } finally {
    global.fetch = previousFetch;
    setAuthTokenProvider(null);
  }
});
