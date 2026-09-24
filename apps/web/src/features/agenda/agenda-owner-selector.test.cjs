const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');
const ts = require('typescript');
const React = require('react');
const root = path.resolve(__dirname, '../..');
const resolve = Module._resolveFilename;
Module._resolveFilename = function (name, ...args) { return resolve.call(this, name.startsWith('@/') ? path.join(root, name.slice(2)) : name, ...args); };
for (const extension of ['.ts', '.tsx']) {
  require.extensions[extension] = (module, filename) => {
    assert.ok(filename.startsWith(root + path.sep));
    module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
    }).outputText, filename);
  };
}
// Drive real handlers and effects using the existing Node runner, without new packages.
let current;
const hooks = { ...React,
  useCallback(callback, deps) {
    const h = current, i = h.index++, previous = h.values[i];
    if (!previous || deps.some((value, index) => !Object.is(value, previous.deps[index]))) h.values[i] = { callback, deps };
    return h.values[i].callback;
  },
  useState(initial) {
    const h = current, i = h.index++;
    if (!(i in h.values)) h.values[i] = initial;
    return [h.values[i], (value) => { h.values[i] = typeof value === 'function' ? value(h.values[i]) : value; }];
  },
  useRef(initial) { const h = current, i = h.index++; return h.values[i] ??= { current: initial }; },
  useEffect(callback, deps) {
    const h = current, i = h.index++, prev = h.effects[i];
    if (!prev || deps.some((v, j) => !Object.is(v, prev.deps[j]))) h.pending.push(() => {
      prev?.cleanup?.(); h.effects[i] = { deps, cleanup: callback() };
    });
  },
};
const load = Module._load;
Module._load = function (name, ...args) { return name === 'react' ? hooks : load.call(this, name, ...args); };
const { OwnerSelector: OwnerAdapter } = require('../../components/owner-selector.tsx');
const { SearchSelector } = require('../../components/search-selector.tsx');
const OwnerSelector = (props) => SearchSelector(OwnerAdapter(props).props);
const { AgendaOwnerSelector } = require('./components/agenda-owner-selector.tsx');
const { appointmentToFormState, selectAppointmentOwner, selectAppointmentPatient } = require('./components/agenda-helpers.ts');
const api = require('../../services/owners.ts');
const { PatientSelector, patientLabel } = require('../../components/patient-selector.tsx');
const { SaleCustomerSelector } = require('../sales/components/sale-customer-selector.tsx');
const { SaleOwnerSelector } = require('../sales/components/sale-owner-selector.tsx');
const patientsApi = require('../../services/patients.ts');
Module._load = load;
function mount(component, props) {
  const h = { values: [], effects: [], pending: [], props };
  h.render = () => { h.index = 0; current = h; h.tree = component(h.props); h.pending.splice(0).forEach((run) => run()); };
  h.dispose = () => h.effects.forEach((e) => e.cleanup?.());
  h.render(); return h;
}
function nodes(n) { return Array.isArray(n) ? n.flatMap(nodes) : n && typeof n === 'object' ? [n, ...nodes(n.props?.children)] : []; }
function text(n) { return Array.isArray(n) ? n.map(text).join('') : n && typeof n === 'object' ? text(n.props?.children) : typeof n === 'string' || typeof n === 'number' ? String(n) : ''; }
const find = (h, predicate) => nodes(h.tree).find(predicate);
const tick = async () => { for (let i = 0; i < 6; i++) await Promise.resolve(); };

test('partial search finds an owner beyond the first page; alphabetical paging, loading, empty and error states', async () => {
  const original = api.getOwners;
  const timers = new Map(); let id = 0;
  global.window = { setTimeout(fn, delay) { timers.set(++id, { fn, delay }); return id; }, clearTimeout(i) { timers.delete(i); } };
  global.document = { addEventListener() {}, removeEventListener() {}, getElementById() { return null; } };
  const requests = [], fixture = Array.from({ length: 65 }, (_, i) => ({ id: String(i), full_name: `Propietario ${String(i).padStart(2, '0')}` }));
  fixture.push({ id: 'zulema', full_name: 'Zulema Torres' });
  let fail = false, selected;
  api.getOwners = async (options) => {
    requests.push(options);
    if (fail) throw new Error('offline');
    assert.equal(options.sortBy, 'full_name'); assert.equal(options.pageSize, 30);
    const matches = fixture.filter((o) => o.full_name.toLowerCase().includes(options.search ?? ''));
    return { data: matches.slice((options.page - 1) * 30, options.page * 30), meta: { total: matches.length } };
  };
  const h = mount(OwnerSelector, { idPrefix: 'agenda-owner', emptyLabel: 'Sin propietario seleccionado', ownerId: '', ownerName: '', onSelect(o) { selected = o; } });
  const flush = async () => { for (const [i, timer] of [...timers]) { timers.delete(i); timer.fn(); } await tick(); h.render(); };
  const click = (label) => { find(h, (n) => n.type === 'button' && text(n) === label).props.onClick(); h.render(); };
  const open = () => { find(h, (n) => n.props?.id === 'agenda-owner-trigger').props.onClick(); h.render(); };
  const search = (value) => { find(h, (n) => n.props?.role === 'combobox').props.onChange({ target: { value } }); h.render(); };
  try {
    assert.equal(requests.length, 0); open(); assert.match(text(h.tree), /Buscando propietarios/); await flush();
    assert.equal(nodes(h.tree).filter((n) => n.props?.role === 'option').length, 30);
    const names = nodes(h.tree).filter((n) => n.props?.role === 'option').map(text);
    assert.deepEqual(names, fixture.slice(0, 30).map((owner) => owner.full_name));
    assert.deepEqual(names, [...names].sort());
    assert.ok(!text(h.tree).includes('Zulema'));
    click('Siguiente'); await flush(); assert.equal(requests.at(-1).page, 2); assert.match(text(h.tree), /Propietario 30/);
    search('  torr  '); assert.equal([...timers.values()][0].delay, 350); assert.equal(requests.length, 2);
    await flush(); assert.equal(requests.at(-1).search, 'torr'); assert.equal(requests.at(-1).page, 1);
    find(h, (n) => n.props?.role === 'option').props.onClick(); h.render(); assert.equal(selected.id, 'zulema');
    h.props = { ...h.props, ownerId: selected.id, ownerName: selected.full_name }; h.render(); open();
    search('missing'); await flush(); assert.match(text(h.tree), /No encontramos propietarios/); assert.match(text(h.tree), /Zulema Torres/);
    fail = true; search('torr'); await flush(); assert.ok(find(h, (n) => n.props?.role === 'alert'));
    fail = false; click('Reintentar'); await flush(); assert.equal(nodes(h.tree).filter((n) => n.props?.role === 'option').length, 1);
    assert.ok(nodes(h.tree).filter((n) => n.type === 'button').every((n) => n.props.type === 'button'));
  } finally { h.dispose(); api.getOwners = original; delete global.window; delete global.document; }
});

test('editing preserves the saved owner ID and label independently of pages, and ignores stale patient-owner lookups', async () => {
  const original = api.getOwner, requests = [], selected = []; let resolveOld;
  api.getOwner = (id) => {
    requests.push(id);
    return id === 'old' ? new Promise((resolve) => { resolveOld = resolve; }) : Promise.resolve({ data: { id, full_name: 'Zulema Torres' } });
  };
  const form = appointmentToFormState({ owner_id: 'outside-first-page', start_at: '2026-09-23T12:00:00Z', end_at: '2026-09-23T12:30:00Z' });
  const h = mount(AgendaOwnerSelector, { ownerId: form.owner_id, onSelect(o) { selected.push(o); } });
  try {
    assert.equal(h.tree.props.ownerId, 'outside-first-page'); await tick(); h.render();
    assert.equal(h.tree.props.ownerName, 'Zulema Torres'); assert.deepEqual(requests, ['outside-first-page']); assert.deepEqual(selected, []);
    h.props.ownerId = 'old'; h.render(); h.props.ownerId = 'new-patient-owner'; h.render(); await tick(); h.render();
    resolveOld({ data: { id: 'old', full_name: 'Stale name' } }); await tick(); h.render();
    assert.equal(h.tree.props.ownerId, 'new-patient-owner'); assert.equal(h.tree.props.ownerName, 'Zulema Torres');
    h.tree.props.onSelect(null); h.props.ownerId = ''; h.render(); assert.equal(h.tree.props.ownerName, '');
    assert.equal(h.tree.props.emptyLabel, 'Sin propietario seleccionado'); assert.deepEqual(selected, [null]);
  } finally { h.dispose(); api.getOwner = original; }
});

test('patient search uses partial text and name order, reaches later pages and distinguishes identical names', async () => {
  const original = patientsApi.getPatients;
  const timers = new Map(); let timerId = 0;
  global.window = { setTimeout(fn, delay) { timers.set(++timerId, { fn, delay }); return timerId; }, clearTimeout(id) { timers.delete(id); } };
  global.document = { addEventListener() {}, removeEventListener() {}, getElementById() { return null; } };
  const fixture = Array.from({ length: 65 }, (_, i) => ({ id: String(i), name: `Mascota ${String(i).padStart(2, '0')}`, owner_id: `owner-${i}`, owner_name: `Propietario ${i}`, species: 'dog' }));
  fixture.push({ id: 'z1', name: 'Zafiro', owner_id: 'ana', owner_name: 'Ana Perez', species: 'dog' },
    { id: 'z2', name: 'Zafiro', owner_id: 'maria', owner_name: 'Maria Torres', species: 'dog' });
  const requests = []; let selected;
  patientsApi.getPatients = async (options) => {
    requests.push(options);
    const rows = fixture.filter((p) => p.name.toLowerCase().includes(options.search ?? ''));
    return { data: rows.slice((options.page - 1) * options.pageSize, options.page * options.pageSize), meta: { total: rows.length } };
  };
  const adapter = mount(PatientSelector, { patientId: '', idPrefix: 'agenda-patient', onSelect(p) { selected = p; } });
  const h = mount(SearchSelector, adapter.tree.props);
  const flush = async () => { for (const [id, timer] of [...timers]) { timers.delete(id); timer.fn(); } await tick(); h.render(); };
  const search = (value) => { find(h, (n) => n.props?.role === 'combobox').props.onChange({ target: { value } }); h.render(); };
  try {
    assert.equal(requests.length, 0);
    find(h, (n) => n.props?.id === 'agenda-patient-trigger').props.onClick(); h.render();
    assert.match(text(h.tree), /Buscando pacientes/); await flush();
    assert.deepEqual(requests[0], { search: undefined, page: 1, pageSize: 30, sortBy: 'name' });
    const names = nodes(h.tree).filter((n) => n.props?.role === 'option').map(text);
    assert.deepEqual(names, fixture.slice(0, 30).map(patientLabel));
    assert.ok(!text(h.tree).includes('Zafiro'));
    find(h, (n) => n.type === 'button' && text(n) === 'Siguiente').props.onClick(); h.render(); await flush();
    assert.equal(requests.at(-1).page, 2); assert.match(text(h.tree), /Mascota 30/);
    search('  zaf  '); assert.equal([...timers.values()][0].delay, 350); await flush();
    assert.equal(requests.at(-1).page, 1); assert.equal(requests.at(-1).search, 'zaf');
    assert.match(text(h.tree), /Zafiro · dog · Ana Perez/); assert.match(text(h.tree), /Zafiro · dog · Maria Torres/);
    find(h, (n) => n.props?.role === 'option' && text(n).includes('Maria')).props.onClick(); h.render();
    assert.equal(selected.id, 'z2'); assert.equal(selected.owner_id, 'maria');
    find(h, (n) => n.props?.id === 'agenda-patient-trigger').props.onClick(); h.render(); search('missing'); await flush();
    assert.match(text(h.tree), /No encontramos pacientes/);
    assert.equal(nodes(h.tree).filter((n) => n.props?.role === 'option').length, 0);
  } finally { h.dispose(); adapter.dispose(); patientsApi.getPatients = original; delete global.window; delete global.document; }
});

test('Agenda editing keeps its patient outside loaded pages; a saved sale label avoids a redundant lookup', async () => {
  const original = patientsApi.getPatient, requests = [], selections = [];
  patientsApi.getPatient = async (id) => { requests.push(id); return { data: { id, name: 'Luna', species: 'cat', owner_id: 'maria' } }; };
  const form = appointmentToFormState({ patient_id: 'outside-first-page', owner_id: 'maria', start_at: '2026-09-23T12:00:00Z', end_at: '2026-09-23T12:30:00Z' });
  const h = mount(PatientSelector, { patientId: form.patient_id, idPrefix: 'agenda-patient', onSelect(p) { selections.push(p); } });
  let sale;
  try {
    assert.equal(h.tree.props.selectedId, 'outside-first-page'); await tick(); h.render();
    assert.equal(h.tree.props.selectedLabel, 'Luna · cat'); assert.deepEqual(selections, []);
    sale = mount(PatientSelector, { patientId: 'saved-sale-patient', patientName: 'Luna snapshot', idPrefix: 'sale-patient', onSelect() {} });
    assert.equal(sale.tree.props.selectedId, 'saved-sale-patient'); assert.equal(sale.tree.props.selectedLabel, 'Luna snapshot');
    assert.deepEqual(requests, ['outside-first-page']);
  } finally { h.dispose(); sale?.dispose(); patientsApi.getPatient = original; }
});

test('Sales selects both existing relations from a patient and clears an incompatible patient on owner change', () => {
  let value = { ownerId: 'old-owner', ownerName: 'Old owner', patientId: 'old-patient', patientName: 'Saved name' };
  const render = () => ({ tree: SaleCustomerSelector({ value, onChange(next) { value = next; } }) });
  let h = render();
  assert.equal(find(h, (n) => n.type === PatientSelector).props.patientName, 'Saved name');
  assert.equal(find(h, (n) => n.type === SaleOwnerSelector).props.disabled, true);
  find(h, (n) => n.type === PatientSelector).props.onSelect(null);
  h = render();
  assert.equal(find(h, (n) => n.type === SaleOwnerSelector).props.disabled, false);
  find(h, (n) => n.type === SaleOwnerSelector).props.onSelect(null);
  h = render();
  find(h, (n) => n.type === PatientSelector).props.onSelect({ id: 'new-patient', name: 'Luna', owner_id: 'new-owner', owner_name: 'Maria Torres' });
  assert.deepEqual(value, { ownerId: 'new-owner', ownerName: 'Maria Torres', patientId: 'new-patient', patientName: 'Luna' });
  h = render(); find(h, (n) => n.type === SaleOwnerSelector).props.onSelect({ id: 'new-owner', full_name: 'Maria Torres' });
  assert.equal(value.patientId, 'new-patient');
  h = render(); find(h, (n) => n.type === SaleOwnerSelector).props.onSelect({ id: 'another-owner', full_name: 'Ana' });
  assert.equal(value.patientId, ''); assert.equal(value.patientName, '');
  h = render(); find(h, (n) => n.type === PatientSelector).props.onSelect(null);
  assert.equal(value.ownerId, 'another-owner');
  h = render(); find(h, (n) => n.type === SaleOwnerSelector).props.onSelect(null);
  assert.equal(value.ownerId, ''); assert.equal(value.patientId, '');
});

test('patient service sends search, page size and opt-in name ordering', async () => {
  const previousFetch = global.fetch;
  const { setAuthTokenProvider } = require('../../lib/api.ts');
  setAuthTokenProvider(async () => 'test-token');
  let query;
  global.fetch = async (url) => {
    query = Object.fromEntries(new URL(url).searchParams);
    return new Response(JSON.stringify({ data: [], meta: { total: 0 } }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
  try {
    await patientsApi.getPatients({ search: 'lun', page: 3, pageSize: 30, sortBy: 'name' });
    assert.deepEqual(query, { search: 'lun', page: '3', page_size: '30', sort_by: 'name' });
  } finally { global.fetch = previousFetch; setAuthTokenProvider(null); }
});

test('patient selector scopes every page/search to its owner and resets search state when scope changes', async () => {
  const original = patientsApi.getPatients;
  const requests = [], selected = [];
  const patients = [{ id: 'p-a', owner_id: 'a', name: 'Luna' }, { id: 'p-b', owner_id: 'b', name: 'Luna' }];
  patientsApi.getPatients = async (options) => {
    requests.push(options);
    return { data: patients.filter((patient) => !options.ownerId || patient.owner_id === options.ownerId), meta: { total: 1 } };
  };
  const h = mount(PatientSelector, { ownerId: 'a', patientId: '', idPrefix: 'test', onSelect(p) { selected.push(p); } });
  try {
    const aKey = h.tree.key;
    const aLoader = h.tree.props.loadPage;
    let results = await aLoader({ search: 'lun', page: 2, pageSize: 30 });
    assert.deepEqual(results.data.map((p) => p.id), ['p-a']);
    assert.deepEqual(requests.at(-1), { ownerId: 'a', search: 'lun', page: 2, pageSize: 30, sortBy: 'name' });
    h.render(); assert.equal(h.tree.props.loadPage, aLoader);
    h.tree.props.onSelect(patients[1]); assert.deepEqual(selected, []);
    h.props.ownerId = 'b'; h.render();
    assert.notEqual(h.tree.key, aKey); // React unmounts the old dropdown, cancelling pending requests and resetting page/query.
    results = await h.tree.props.loadPage({ page: 1, pageSize: 30 });
    assert.deepEqual(results.data.map((p) => p.id), ['p-b']);
    h.props.ownerId = ''; h.render();
    assert.equal(h.tree.key, 'all-patients');
    results = await h.tree.props.loadPage({ page: 1, pageSize: 30 });
    assert.equal('ownerId' in requests.at(-1), false);
    assert.equal(results.data.length, 2);
    h.tree.props.onSelect(patients[1]); assert.equal(selected[0].owner_id, 'b');
  } finally { h.dispose(); patientsApi.getPatients = original; }
});

test('Agenda keeps valid pairs when choosing, changing or clearing either party, including editing', () => {
  let form = appointmentToFormState({ owner_id: 'a', patient_id: 'pa', start_at: '2026-09-23T12:00:00Z', end_at: '2026-09-23T12:30:00Z' });
  assert.equal(form.patient_id, 'pa'); assert.equal(form.owner_id, 'a');
  assert.equal(selectAppointmentOwner(form, { id: 'a' }).patient_id, 'pa');
  form = selectAppointmentOwner(form, { id: 'b' });
  assert.equal(form.owner_id, 'b'); assert.equal(form.patient_id, '');
  assert.equal(selectAppointmentPatient(form, { id: 'pa', owner_id: 'a' }), form);
  form = selectAppointmentPatient(form, { id: 'pb', owner_id: 'b' });
  assert.equal(form.patient_id, 'pb'); assert.equal(form.owner_id, 'b');
  form = selectAppointmentPatient(form, null);
  assert.equal(form.patient_id, ''); assert.equal(form.owner_id, 'b');
  form = selectAppointmentOwner(form, null);
  assert.equal(form.owner_id, ''); assert.equal(form.patient_id, '');
  form = selectAppointmentPatient(form, { id: 'pa', owner_id: 'a' });
  assert.equal(form.owner_id, 'a'); assert.equal(form.patient_id, 'pa');
  form = selectAppointmentOwner(form, null);
  assert.equal(form.patient_id, '');
});

test('Sales filters by its selected owner and rejects incompatible patient callbacks', () => {
  let value = { ownerId: '', ownerName: '', patientId: '', patientName: '' };
  const render = () => ({ tree: SaleCustomerSelector({ value, onChange(next) { value = next; } }) });
  let h = render();
  assert.equal(find(h, (n) => n.type === PatientSelector).props.ownerId, '');
  find(h, (n) => n.type === SaleOwnerSelector).props.onSelect({ id: 'a', full_name: 'Ana' });
  h = render(); assert.equal(value.patientId, '');
  assert.equal(find(h, (n) => n.type === PatientSelector).props.ownerId, 'a');
  find(h, (n) => n.type === PatientSelector).props.onSelect({ id: 'pb', owner_id: 'b', name: 'Luna' });
  assert.equal(value.ownerId, 'a'); assert.equal(value.patientId, '');
  find(h, (n) => n.type === PatientSelector).props.onSelect({ id: 'pa', owner_id: 'a', owner_name: 'Ana', name: 'Luna' });
  h = render(); assert.equal(find(h, (n) => n.type === SaleOwnerSelector).props.disabled, true);
  assert.equal(find(h, (n) => n.type === PatientSelector).props.patientId, 'pa');
  find(h, (n) => n.type === PatientSelector).props.onSelect(null);
  h = render(); assert.equal(find(h, (n) => n.type === SaleOwnerSelector).props.disabled, false);
  find(h, (n) => n.type === SaleOwnerSelector).props.onSelect(null);
  h = render(); assert.equal(find(h, (n) => n.type === PatientSelector).props.ownerId, '');
});

test('a locked owner selector cannot open or issue searches', () => {
  const original = api.getOwners; let requests = 0;
  api.getOwners = async () => { requests++; return { data: [], meta: { total: 0 } }; };
  global.document = { addEventListener() {}, removeEventListener() {} };
  const h = mount(OwnerSelector, { disabled: true, ownerId: 'a', ownerName: 'Ana', onSelect() { assert.fail('locked'); } });
  try {
    const trigger = find(h, (n) => n.props?.id === 'sale-owner-trigger');
    assert.equal(trigger.props.disabled, true);
    trigger.props.onClick(); h.render();
    assert.equal(find(h, (n) => n.props?.role === 'combobox'), undefined);
    assert.equal(requests, 0);
  } finally { h.dispose(); api.getOwners = original; delete global.document; }
});
