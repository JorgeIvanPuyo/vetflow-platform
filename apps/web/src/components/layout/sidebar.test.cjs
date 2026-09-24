const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');
const ts = require('typescript');
const React = require('react');
require.extensions['.css'] = (module) => { module.exports = {}; };
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
  useMemo(callback, deps) {
    const h = current, i = h.index++, previous = h.values[i];
    if (!previous || deps.some((value, index) => !Object.is(value, previous.deps[index]))) h.values[i] = { value: callback(), deps };
    return h.values[i].value;
  },
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


require.extensions['.css'] = module => { module.exports = { __esModule: true, default: new Proxy({}, { get: (_, key) => key }) }; };
let pathname = '/inventory/product-1', role = 'clinic_admin', logouts = 0;
const user = { displayName: 'María', email: 'maria@example.test' };
const load = Module._load;
Module._load = function (name, ...args) {
  if (name === 'react') return hooks;
  if (name === 'next/navigation') return { usePathname: () => pathname };
  if (name === '@/features/auth/auth-context') return { useAuth: () => ({ user, logout() { logouts += 1; } }) };
  if (name === '@/features/auth/current-user-context') return { useCurrentUser: () => ({ role }) };
  if (name === '@/features/clinic/clinic-context') return { useClinic: () => ({ displayName: 'Clínica', profile: null, refreshProfile() {} }) };
  if (name === '@/features/search/components/global-search') return { GlobalSearch: () => null };
  return load.call(this, name, ...args);
};
const { AppSidebar } = require('./app-sidebar.tsx');
const { AppHeader } = require('./app-header.tsx');
const { UserSessionFooter } = require('./user-session-footer.tsx');
const { navigationItems, filterNavigationByRole } = require('./navigation-items.ts');
Module._load = load;
function mount(component, props, attach) {
  const h = { values: [], effects: [], pending: [], props };
  h.render = () => { h.index = 0; current = h; h.tree = component(h.props); attach?.(h.tree); h.pending.splice(0).forEach((run) => run()); };
  h.dispose = () => h.effects.forEach((e) => e.cleanup?.());
  h.render(); return h;
}
function nodes(n) { return Array.isArray(n) ? n.flatMap(nodes) : n && typeof n === 'object' ? [n, ...nodes(n.props?.children)] : []; }
function text(n) { return Array.isArray(n) ? n.map(text).join('') : n && typeof n === 'object' ? text(n.props?.children) : typeof n === 'string' || typeof n === 'number' ? String(n) : ''; }
const find = (h, predicate) => nodes(h.tree).find(predicate);
const tick = async () => { for (let i = 0; i < 6; i++) await Promise.resolve(); };

function storage(initial) {
  const values = new Map(initial === undefined ? [] : [['vetflow:sidebar-collapsed', initial]]);
  global.window = {
    localStorage: { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) },
    addEventListener() {}, removeEventListener() {},
  };
  return values;
}
const toggle = h => find(h, n => n.props?.['aria-controls'] === 'desktop-navigation');
const links = h => nodes(h.tree).filter(n => n.props?.className?.includes('app-sidebar__link'));
function clickToggle(h) { toggle(h).props.onClick(); h.render(); }

test('default sidebar is expanded; native button collapses/expands and persists only its visual preference', () => {
  const values = storage(); const h = mount(AppSidebar);
  assert.equal(toggle(h).props['aria-expanded'], true);
  assert.equal(h.tree.props.className.includes('collapsed'), false);
  assert.equal(values.size, 0);
  clickToggle(h);
  assert.equal(toggle(h).type, 'button'); assert.equal(toggle(h).props.type, 'button');
  assert.equal(toggle(h).props['aria-label'], 'Expandir navegación');
  assert.equal(toggle(h).props['aria-expanded'], false);
  assert.ok(h.tree.props.className.includes('collapsed'));
  assert.equal(values.get('vetflow:sidebar-collapsed'), 'true');
  clickToggle(h);
  assert.equal(toggle(h).props['aria-label'], 'Colapsar navegación');
  assert.equal(toggle(h).props['aria-expanded'], true);
  assert.equal(values.get('vetflow:sidebar-collapsed'), 'false'); assert.equal(values.size, 1); h.dispose();
});

test('stored preference is restored after the first render; invalid values and blocked storage remain usable', () => {
  storage('true'); let h = mount(AppSidebar);
  assert.equal(toggle(h).props['aria-expanded'], true); // server/first client render agree
  h.render(); assert.equal(toggle(h).props['aria-expanded'], false); h.dispose();
  storage('invalid'); h = mount(AppSidebar); h.render(); assert.equal(toggle(h).props['aria-expanded'], true); h.dispose();
  storage(); window.localStorage = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  h = mount(AppSidebar); h.render(); clickToggle(h); assert.equal(toggle(h).props['aria-expanded'], false); h.dispose();
});

test('collapsed links preserve destinations, active section, accessible names and hover/keyboard tooltip labels', () => {
  storage(); const h = mount(AppSidebar);
  const before = links(h).map(n => n.props.href); clickToggle(h);
  assert.deepEqual(links(h).map(n => n.props.href), before);
  assert.deepEqual(before, filterNavigationByRole(navigationItems, role).map(n => n.href));
  for (const link of links(h)) {
    assert.equal(link.props['data-sidebar-tooltip'], link.props['aria-label']);
    assert.ok(nodes(link).some(n => n.props?.className === 'linkLabel'));
  }
  const active = links(h).filter(n => n.props['aria-current'] === 'page');
  assert.equal(active.length, 1); assert.equal(active[0].props.href, '/inventory/dashboard');
  assert.ok(active[0].props.className.includes('app-sidebar__link--active'));
  pathname = '/suppliers/one'; h.render(); assert.equal(links(h).find(n => n.props['aria-current'] === 'page').props.href, '/purchases/dashboard');
  pathname = '/'; h.render(); assert.equal(links(h).find(n => n.props['aria-current'] === 'page').props.href, '/');
  pathname = '/inventory/product-1'; h.dispose();
});

test('compact session retains logout and superadmin can expand to reach the unchanged clinic selector', () => {
  storage(); role = 'superadmin'; const h = mount(AppSidebar); clickToggle(h);
  const footer = find(h, n => n.type === UserSessionFooter);
  const tree = UserSessionFooter(footer.props);
  const logout = nodes(tree).find(n => n.props?.['aria-label'] === 'Cerrar sesión');
  assert.equal(logout.props['data-sidebar-tooltip'], 'Cerrar sesión'); logout.props.onClick(); assert.equal(logouts, 1);
  assert.match(tree.props.title, /María/);
  find(h, n => n.props?.['aria-label'] === 'Expandir para cambiar clínica').props.onClick(); h.render();
  assert.equal(toggle(h).props['aria-expanded'], true);
  h.dispose(); role = 'clinic_admin';
});

test('mobile header keeps its independent menu, text links and close-on-navigation behavior', () => {
  storage('true'); const h = mount(AppHeader);
  const trigger = find(h, n => n.props?.className === 'icon-button menu-trigger'); assert.ok(trigger);
  trigger.props.onClick(); h.render();
  const mobileLinks = nodes(h.tree).filter(n => n.props?.className === 'mobile-menu__link');
  assert.deepEqual(mobileLinks.map(n => n.props.href), navigationItems.map(n => n.href));
  for (const link of mobileLinks) assert.ok(text(link).trim());
  mobileLinks[0].props.onClick(); h.render();
  assert.equal(find(h, n => n.props?.className === 'mobile-menu-overlay'), undefined); h.dispose();
});

test('collapse styling is desktop-only and reduces both width and flex basis with focus/tooltip support', () => {
  const css = fs.readFileSync(path.join(__dirname, 'app-sidebar.module.css'), 'utf8');
  assert.match(css, /^@media \(min-width: 1024px\)/);
  assert.match(css, /\.sidebar\.collapsed\s*\{[^}]*width: 76px; flex-basis: 76px; padding: 0;/);
  assert.match(css, /\.collapsed \.linkLabel/); assert.match(css, /display: none/);
  assert.match(css, /:focus-visible/); assert.match(css, /:hover, :focus-visible/);
  assert.match(css, /prefers-reduced-motion: reduce/);
});
