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
for (const extension of ['.ts', '.tsx']) require.extensions[extension] = (module, filename) => {
  assert.ok(filename.startsWith(root + path.sep));
  module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { fileName: filename,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText, filename);
};
// Follow the existing agenda selector tests: real handlers/effects, no new dependencies.
let current;
const hooks = { ...React,
  useState(initial) { const h = current, i = h.index++; if (!(i in h.values)) h.values[i] = typeof initial === 'function' ? initial() : initial; return [h.values[i], (v) => { h.values[i] = typeof v === 'function' ? v(h.values[i]) : v; }]; },
  useRef(initial) { const h = current, i = h.index++; return h.values[i] ??= { current: initial }; },
  useCallback(callback, deps) { const h = current, i = h.index++, p = h.values[i]; if (!p || deps.some((v, j) => !Object.is(v, p.deps[j]))) h.values[i] = { callback, deps }; return h.values[i].callback; },
  useEffect(callback, deps) { const h = current, i = h.index++, p = h.effects[i]; if (!p || deps.some((v, j) => !Object.is(v, p.deps[j]))) h.pending.push(() => { p?.cleanup?.(); h.effects[i] = { deps, cleanup: callback() }; }); },
};
const load = Module._load;
const stubs = {
  '@/features/auth/current-user-context': { useCurrentUser: () => ({ role: 'medico_veterinario' }) },
  '@/features/owners/hooks/use-refresh-on-return': { useRefreshOnReturn() {} },
  '@/features/patients/components/patient-photo': { PatientAvatar() {}, PatientPhotoInput() {} },
  '@/features/owners/components/receivable-badge': { ReceivableBadge() {} },
};
Module._load = function (name, ...args) { return name === 'react' ? hooks : stubs[name] ?? load.call(this, name, ...args); };
const { PatientsScreen } = require('./components/patients-screen.tsx');
const { OwnerSelector } = require('../../components/owner-selector.tsx');
const { SearchSelector } = require('../../components/search-selector.tsx');
const ownersApi = require('../../services/owners.ts');
const patientsApi = require('../../services/patients.ts');
const catalogsApi = require('../../services/catalogs.ts');
Module._load = load;
function mount(component, props = {}) { const h = { values: [], effects: [], pending: [], props }; h.render = () => { h.index = 0; current = h; h.tree = component(h.props); h.pending.splice(0).forEach((run) => run()); }; h.dispose = () => h.effects.forEach((e) => e.cleanup?.()); h.render(); return h; }
function nodes(n) { return Array.isArray(n) ? n.flatMap(nodes) : n && typeof n === 'object' ? [n, ...nodes(n.props?.children)] : []; }
function text(n) { return Array.isArray(n) ? n.map(text).join('') : n && typeof n === 'object' ? text(n.props?.children) : typeof n === 'string' || typeof n === 'number' ? String(n) : ''; }
const find = (h, p) => nodes(h.tree).find(p);
const tick = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
const button = (h, label) => find(h, (n) => n.type === 'button' && text(n) === label);
const field = (h, label) => nodes(find(h, (n) => n.type === 'label' && text(n).startsWith(label))).find((n) => n.type === 'input');
function mockScreenApis() { const originals = [ownersApi, patientsApi, catalogsApi].map((api) => ({ ...api })); ownersApi.getOwners = () => assert.fail('The screen must not preload the owner catalog'); patientsApi.getPatients = async () => ({ data: [{ id: 'p', owner_id: 'server-owner', owner_name: 'Nombre del servidor', name: 'Luna', species: 'Canino' }], meta: { page: 1, page_size: 12, total: 1 } }); catalogsApi.getCatalogItems = async () => ({ data: [] }); return () => [ownersApi, patientsApi, catalogsApi].forEach((api, i) => Object.assign(api, originals[i])); }

test('patient creation sends the remote selection ID, preserves the form and resets after creation/cancel', async () => {
  const restore = mockScreenApis(), payloads = [];
  patientsApi.createPatient = async (payload) => { payloads.push(payload); return { data: { id: 'created' } }; };
  const h = mount(PatientsScreen);
  try {
    await tick(); h.render(); assert.match(text(h.tree), /Nombre del servidor/);
    find(h, (n) => n.props?.['aria-label'] === 'Crear paciente').props.onClick(); h.render();
    let selector = find(h, (n) => n.type === OwnerSelector);
    assert.equal(selector.props.ownerId, ''); assert.equal(selector.props.idPrefix, 'patient-owner'); assert.equal(selector.props.defaultOpen, true);
    assert.deepEqual(selector.props.messages, { loading: 'Cargando propietarios…', empty: 'No se encontraron propietarios', error: 'Error al buscar propietarios' });
    assert.equal(button(h, 'Crear paciente').props.disabled, true);
    field(h, 'Nombre del paciente').props.onChange({ target: { value: ' Paciente prueba ' } }); button(h, 'Canino').props.onClick(); h.render();
    selector.props.onSelect({ id: 'outside-first-page', full_name: 'Zulema Torres', phone: '555' }); h.render();
    selector = find(h, (n) => n.type === OwnerSelector);
    assert.equal(selector.props.ownerId, 'outside-first-page'); assert.equal(selector.props.ownerName, 'Zulema Torres · 555');
    assert.equal(field(h, 'Nombre del paciente').props.value, ' Paciente prueba '); assert.equal(button(h, 'Crear paciente').props.disabled, false);
    await find(h, (n) => n.type === 'form').props.onSubmit({ preventDefault() {} }); h.render();
    assert.deepEqual(payloads, [{ owner_id: 'outside-first-page', name: 'Paciente prueba', species: 'Canino' }]);
    assert.equal(find(h, (n) => n.props?.role === 'dialog'), undefined);
    find(h, (n) => n.props?.['aria-label'] === 'Crear paciente').props.onClick(); h.render();
    selector = find(h, (n) => n.type === OwnerSelector); assert.equal(selector.props.ownerId, ''); assert.equal(selector.props.ownerName, '');
    selector.props.onSelect({ id: 'another', full_name: 'Ana', phone: '1' }); h.render(); button(h, 'Cancelar').props.onClick(); h.render();
    find(h, (n) => n.props?.['aria-label'] === 'Crear paciente').props.onClick(); h.render(); assert.equal(find(h, (n) => n.type === OwnerSelector).props.ownerId, '');
  } finally { h.dispose(); restore(); }
});

test('inline owner creation selects ID and name without a catalog reload; clearing requires reselection', async () => {
  const restore = mockScreenApis(); ownersApi.createOwner = async () => ({ data: { id: 'inline', full_name: 'Nueva propietaria', phone: '123' } });
  const h = mount(PatientsScreen);
  try {
    await tick(); h.render(); find(h, (n) => n.props?.['aria-label'] === 'Crear paciente').props.onClick(); h.render();
    field(h, 'Nombre del paciente').props.onChange({ target: { value: 'Paciente en curso' } }); h.render(); button(h, '+ Crear nuevo propietario').props.onClick(); h.render();
    field(h, 'Nombre completo').props.onChange({ target: { value: 'Nueva propietaria' } }); field(h, 'Teléfono').props.onChange({ target: { value: '123' } }); h.render();
    await find(h, (n) => n.type === 'form').props.onSubmit({ preventDefault() {} }); h.render();
    const selector = find(h, (n) => n.type === OwnerSelector); assert.equal(selector.props.ownerId, 'inline'); assert.equal(selector.props.ownerName, 'Nueva propietaria · 123');
    assert.equal(field(h, 'Nombre del paciente').props.value, 'Paciente en curso'); selector.props.onSelect(null); h.render();
    assert.equal(find(h, (n) => n.type === OwnerSelector).props.ownerId, ''); assert.equal(button(h, 'Crear paciente').props.disabled, true); assert.ok(button(h, '+ Crear nuevo propietario'));
  } finally { h.dispose(); restore(); }
});

test('remote owner search debounces, ignores old success/error responses, pages, preserves selection and recovers', async () => {
  const original = ownersApi.getOwners, timers = new Map(), requests = []; let timerId = 0, resolveOld, rejectOld, fail = false;
  global.window = { setTimeout(fn, delay) { timers.set(++timerId, { fn, delay }); return timerId; }, clearTimeout(id) { timers.delete(id); } };
  global.document = { addEventListener() {}, removeEventListener() {}, getElementById() { return null; } };
  ownersApi.getOwners = (options, requestOptions) => {
    assert.deepEqual(requestOptions, { retryTransient: false });
    requests.push(options);
    if (options.search === 'old') return new Promise((resolve, reject) => { resolveOld = resolve; rejectOld = reject; });
    if (fail) return Promise.reject(new Error('offline'));
    const data = options.search === 'new' ? [{ id: 'later', full_name: 'Later owner' }] : options.search ? [] : Array.from({ length: 30 }, (_, i) => ({ id: `${options.page}-${i}`, full_name: `Owner ${options.page}-${i}` }));
    return Promise.resolve({ data, meta: { total: options.search ? data.length : 65 } });
  };
  const h = mount((props) => SearchSelector(OwnerSelector(props).props), { defaultOpen: true, idPrefix: 'patient-owner', emptyLabel: 'Selecciona un propietario', ownerId: 'saved', ownerName: 'Saved owner', onSelect(owner) { h.props = { ...h.props, ownerId: owner?.id ?? '', ownerName: owner?.full_name ?? '' }; } });
  const flush = async () => { for (const [id, timer] of [...timers]) { timers.delete(id); timer.fn(); } await tick(); h.render(); };
  const open = () => { find(h, (n) => n.props?.id === 'patient-owner-trigger').props.onClick(); h.render(); };
  const search = (value) => { find(h, (n) => n.props?.role === 'combobox').props.onChange({ target: { value } }); h.render(); };
  try {
    assert.equal(requests.length, 0); assert.match(text(h.tree), /Buscando propietarios/); await flush();
    assert.deepEqual(requests[0], { search: undefined, page: 1, pageSize: 30, sortBy: 'full_name' }); assert.equal(nodes(h.tree).filter((n) => n.props?.role === 'option').length, 30);
    button(h, 'Siguiente').props.onClick(); h.render(); await flush(); assert.equal(requests.at(-1).page, 2);
    assert.equal(new Set(nodes(h.tree).filter((n) => n.props?.role === 'option').map((n) => n.props.id)).size, 30);
    search('n'); search('ne'); search('new'); assert.equal(requests.length, 2); assert.equal(timers.size, 1); assert.equal([...timers.values()][0].delay, 350); await flush();
    assert.equal(requests.at(-1).search, 'new'); assert.equal(requests.at(-1).page, 1); assert.match(text(h.tree), /Later owner/);
    search('old'); await flush(); search('new'); await flush(); resolveOld({ data: [{ id: 'stale', full_name: 'Stale owner' }], meta: { total: 1 } }); await tick(); h.render(); assert.ok(!text(h.tree).includes('Stale owner'));
    search('old'); await flush(); search('new'); await flush(); rejectOld(new Error('old failure')); await tick(); h.render(); assert.equal(find(h, (n) => n.props?.role === 'alert'), undefined);
    find(h, (n) => n.props?.role === 'combobox').props.onKeyDown({ key: 'ArrowDown', preventDefault() {} }); h.render(); assert.equal(find(h, (n) => n.props?.role === 'combobox').props['aria-activedescendant'], 'patient-owner-option-later');
    find(h, (n) => n.props?.role === 'combobox').props.onKeyDown({ key: 'Enter', preventDefault() {} }); h.render(); assert.equal(h.props.ownerId, 'later');
    open(); search('missing'); await flush(); assert.match(text(h.tree), /No encontramos propietarios/); assert.match(text(h.tree), /Later owner/);
    fail = true; search('new'); await flush(); assert.ok(find(h, (n) => n.props?.role === 'alert')); assert.equal(h.props.ownerId, 'later');
    fail = false; button(h, 'Reintentar').props.onClick(); h.render(); await flush(); search(''); await flush(); assert.equal(requests.at(-1).search, undefined); assert.equal(requests.at(-1).page, 1);
    search('old'); await flush(); find(h, (n) => n.props?.className === 'sale-product-selector').props.onKeyDown({ key: 'Escape', preventDefault() {}, stopPropagation() {} }); h.render();
    resolveOld({ data: [{ id: 'stale', full_name: 'Stale owner' }], meta: { total: 1 } }); await tick(); h.render(); assert.equal(find(h, (n) => n.props?.role === 'combobox'), undefined); assert.equal(h.props.ownerId, 'later');
  } finally { h.dispose(); ownersApi.getOwners = original; delete global.window; delete global.document; }
});

test('a transient owner search failure stays local and bypasses page recovery', async () => {
  const { setAuthTokenProvider, setPageReadHandler } = require('../../lib/api.ts');
  const previousFetch = global.fetch;
  let fetches = 0;
  setAuthTokenProvider(async () => 'test-token');
  const unregister = setPageReadHandler(() => assert.fail('Interactive search must not hide the page'));
  global.fetch = async () => {
    fetches++;
    return new Response(JSON.stringify({ error: { message: 'Temporarily unavailable' } }), { status: 503 });
  };
  try {
    await assert.rejects(ownersApi.getOwners({ search: 'new', page: 1, pageSize: 30 }, { retryTransient: false }), (error) => error.status === 503);
    assert.equal(fetches, 1);
  } finally { unregister(); setAuthTokenProvider(null); global.fetch = previousFetch; }
});
