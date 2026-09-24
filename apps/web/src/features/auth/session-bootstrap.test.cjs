const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');
const ts = require('typescript');
const root = path.resolve(__dirname, '../..');
const resolve = Module._resolveFilename;
Module._resolveFilename = function (name, ...args) { return resolve.call(this, name.startsWith('@/') ? path.join(root, name.slice(2)) : name, ...args); };
for (const extension of ['.ts', '.tsx']) require.extensions[extension] = (module, filename) => {
  assert.ok(filename.startsWith(root + path.sep));
  module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText, filename);
};
const { validateSession } = require('./session-bootstrap.ts');
const { api, ApiClientError, getApiErrorMessage, setAuthTokenProvider } = require('../../lib/api.ts');
const { getCurrentUser } = require('../../services/auth.ts');
const { SessionStatusScreen } = require('./components/session-status-screen.tsx');
const { renderToStaticMarkup } = require('react-dom/server');
const React = require('react');
const flush = async () => { for (let i = 0; i < 40; i++) await Promise.resolve(); };

function clock() {
  let now = 0, id = 0; const tasks = new Map();
  const original = [global.setTimeout, global.clearTimeout];
  global.setTimeout = (fn, ms) => { tasks.set(++id, { at: now + ms, fn }); return id; };
  global.clearTimeout = id => tasks.delete(id);
  return {
    async advance(ms) {
      await flush(); const end = now + ms;
      while (true) {
        const next = [...tasks].filter(([, task]) => task.at <= end).sort((a, b) => a[1].at - b[1].at)[0];
        if (!next) break;
        now = next[1].at; tasks.delete(next[0]); next[1].fn(); await flush();
      }
      now = end; await flush();
    },
    get now() { return now; }, get pending() { return tasks.size; },
    restore() { [global.setTimeout, global.clearTimeout] = original; },
  };
}
function start(request, refreshToken = async () => {}) {
  const controller = new AbortController(), statuses = [];
  const result = validateSession({ request, refreshToken, signal: controller.signal, onStatus: s => statuses.push(s) });
  return { controller, statuses, result };
}

test('valid session succeeds immediately; network/503 recover automatically after five seconds', async () => {
  const time = clock();
  try {
    assert.deepEqual(await start(async () => 'user').result, { status: 'authenticated', data: 'user' });
    for (const error of [new TypeError('fetch failed'), new ApiClientError('unavailable', 503, 'auth_verification_unavailable')]) {
      let attempts = 0, refreshes = 0;
      const run = start(async () => { if (++attempts === 1) throw error; return 'user'; }, async () => { refreshes++; });
      await flush(); assert.ok(run.statuses.includes('waiting-for-server'));
      await time.advance(4999); assert.equal(attempts, 1); await time.advance(1);
      assert.equal((await run.result).status, 'authenticated'); assert.equal(attempts, 2); assert.equal(refreshes, 0);
      assert.doesNotMatch(getApiErrorMessage(error), /sesión expiró/);
    }
    assert.equal(time.pending, 0);
  } finally { time.restore(); }
});

test('eight fast failures exhaust in 35 seconds; another cycle starts with a fresh budget', async () => {
  const time = clock(); let attempts = 0; const times = [];
  const request = async () => { attempts++; times.push(time.now); throw new ApiClientError('down', 502); };
  try {
    const first = start(request); await time.advance(35000);
    assert.equal((await first.result).status, 'connection-failed'); assert.equal(attempts, 8);
    assert.deepEqual(times, [0, 5000, 10000, 15000, 20000, 25000, 30000, 35000]);
    const second = start(request); await flush(); assert.equal(attempts, 9);
    second.controller.abort(); assert.equal(await second.result, null); assert.equal(time.pending, 0);
  } finally { time.restore(); }
});

test('slow cold start can succeed at 30 seconds; a stuck request aborts at the 40 second global limit', async () => {
  const time = clock();
  try {
    let active = 0, max = 0;
    const successful = start(signal => new Promise((resolve, reject) => {
      active++; max = Math.max(max, active);
      const timer = setTimeout(() => { active--; resolve('user'); }, 30000);
      signal.addEventListener('abort', () => { clearTimeout(timer); reject(signal.reason); }, { once: true });
    }));
    await time.advance(5000); assert.ok(successful.statuses.includes('waiting-for-server'));
    await time.advance(25000); assert.equal((await successful.result).status, 'authenticated'); assert.equal(max, 1);
    let aborted = false, attempts = 0;
    const stuck = start(signal => { attempts++; return new Promise((_, reject) => signal.addEventListener('abort', () => { aborted = true; reject(signal.reason); }, { once: true })); });
    await time.advance(40000); assert.equal((await stuck.result).status, 'connection-failed');
    assert.ok(aborted); assert.equal(attempts, 1); assert.equal(time.pending, 0);
  } finally { time.restore(); }
});

test('requests never overlap and cancellation prevents further attempts and status updates', async () => {
  const time = clock(); let active = 0, max = 0, attempts = 0;
  try {
    const run = start(signal => new Promise((_, reject) => {
      attempts++; active++; max = Math.max(max, active);
      const timer = setTimeout(() => { active--; reject(new TypeError('network')); }, 1000);
      signal.addEventListener('abort', () => { clearTimeout(timer); reject(signal.reason); }, { once: true });
    }));
    await time.advance(13000); assert.equal(attempts, 3); assert.equal(max, 1);
    run.controller.abort(); const states = [...run.statuses]; assert.equal(await run.result, null);
    await time.advance(60000); assert.equal(attempts, 3); assert.deepEqual(run.statuses, states); assert.equal(time.pending, 0);
  } finally { time.restore(); }
});

test('confirmed 401 refreshes exactly once; continued invalidity fails authentication; 403/unknown 401 do not', async () => {
  let attempts = 0, refreshes = 0;
  const invalid = new ApiClientError('invalid', 401, 'invalid_auth_token');
  const run = start(async () => { attempts++; throw invalid; }, async () => { refreshes++; });
  assert.equal((await run.result).status, 'authentication-failed'); assert.equal(attempts, 2); assert.equal(refreshes, 1);
  attempts = 0;
  assert.equal((await start(async () => { if (++attempts === 1) throw invalid; return 'valid'; }).result).status, 'authenticated');
  for (const code of ['forbidden', 'inactive_user', 'user_not_registered']) {
    assert.equal((await start(async () => { throw new ApiClientError('forbidden', 403, code); }).result).status, 'authorization-failed');
  }
  const unknown = new ApiClientError('proxy error', 401);
  assert.equal((await start(async () => { throw unknown; }).result).status, 'connection-failed');
  assert.doesNotMatch(getApiErrorMessage(unknown), /sesión expiró/);
});

test('real session service disables nested retries, preserves bearer token and sends cancellation signal', async () => {
  const time = clock(), previousFetch = global.fetch; let calls = 0;
  setAuthTokenProvider(async () => 'existing-token');
  global.fetch = async (url, init) => {
    calls++; assert.ok(url.endsWith('/api/v1/auth/me')); assert.equal(init.headers.get('Authorization'), 'Bearer existing-token'); assert.ok(init.signal);
    return calls === 1 ? new Response('{}', { status: 503 }) : new Response(JSON.stringify({ data: { id: 'user' } }), { status: 200 });
  };
  try {
    const run = start(getCurrentUser); await flush(); assert.equal(calls, 1);
    await time.advance(5000); assert.equal((await run.result).status, 'authenticated'); assert.equal(calls, 2);
  } finally { time.restore(); global.fetch = previousFetch; setAuthTokenProvider(null); }
});

test('deadline also covers token acquisition and never launches a late HTTP request', async () => {
  const time = clock(), previousFetch = global.fetch; let release, calls = 0;
  setAuthTokenProvider(() => new Promise(resolve => { release = resolve; }));
  global.fetch = async () => { calls++; return new Response('{}'); };
  try {
    const run = start(getCurrentUser); await time.advance(40000);
    assert.equal((await run.result).status, 'connection-failed'); release('late-token'); await flush(); assert.equal(calls, 0);
  } finally { time.restore(); global.fetch = previousFetch; setAuthTokenProvider(null); }
});

test('mutations including blobs/form data never retry network failures or 503 responses', async () => {
  const previousFetch = global.fetch; setAuthTokenProvider(async () => 'token');
  try {
    for (const call of [() => api.post('/sale', {}), () => api.patch('/sale', {}), () => api.delete('/sale'), () => api.postFormData('/file', new FormData()), () => api.patchFormData('/file', new FormData()), () => api.postBlob('/export', {})]) {
      for (const network of [true, false]) {
        let calls = 0; global.fetch = async () => { calls++; if (network) throw new TypeError('offline'); return new Response('{}', { status: 503 }); };
        await assert.rejects(call()); assert.equal(calls, 1);
      }
    }
  } finally { global.fetch = previousFetch; setAuthTokenProvider(null); }
});

test('connection screen offers retry without expired-session wording; authorization and authentication are distinct', () => {
  const render = status => renderToStaticMarkup(React.createElement(SessionStatusScreen, { status }));
  assert.match(render('connection-failed'), /No pudimos conectar con el servidor/);
  assert.match(render('connection-failed'), /Reintentar/); assert.doesNotMatch(render('connection-failed'), /sesión expiró/);
  assert.match(render('waiting-for-server'), /Conectando con el servidor/);
  assert.match(render('authentication-failed'), /sesión expiró/); assert.doesNotMatch(render('authorization-failed'), /sesión expiró/);
});

// Drive the provider's real lifecycle without mounting protected descendants.
let current, requestSession, logoutCalls = 0;
const localUser = { uid: 'user-1', getIdToken: async () => 'refreshed-token' };
const hooks = { ...React,
  useState(initial) {
    const h = current, i = h.index++;
    if (!(i in h.values)) h.values[i] = typeof initial === 'function' ? initial() : initial;
    return [h.values[i], value => { h.values[i] = typeof value === 'function' ? value(h.values[i]) : value; }];
  },
  useRef(initial) { const h = current, i = h.index++; return h.values[i] ??= { current: initial }; },
  useMemo(fn, deps) {
    const h = current, i = h.index++, prev = h.values[i];
    if (!prev || deps.some((v, j) => !Object.is(v, prev.deps[j]))) h.values[i] = { value: fn(), deps };
    return h.values[i].value;
  },
  useCallback(fn, deps) { return hooks.useMemo(() => fn, deps); },
  useEffect(fn, deps) {
    const h = current, i = h.index++, prev = h.effects[i];
    if (!prev || deps.some((v, j) => !Object.is(v, prev.deps[j]))) h.pending.push(() => { prev?.cleanup?.(); h.effects[i] = { deps, cleanup: fn() }; });
  },
};
const originalLoad = Module._load;
Module._load = function (name, ...args) {
  if (name === 'react') return hooks;
  if (name === './auth-context') return { useAuth: () => ({ user: localUser, logout() { logoutCalls++; } }) };
  if (name === '@/lib/acting-tenant') return { applyStoredActingTenant() {} };
  if (name === '@/services/auth') return { getCurrentUser: signal => requestSession(signal) };
  return originalLoad.call(this, name, ...args);
};
const { CurrentUserProvider } = require('./current-user-context.tsx');
Module._load = originalLoad;
function mountGate() {
  const h = { values: [], effects: [], pending: [] };
  h.render = () => { h.index = 0; current = h; h.tree = CurrentUserProvider({ children: 'protected application' }); h.pending.splice(0).forEach(fn => fn()); };
  h.dispose = () => h.effects.forEach(e => e.cleanup?.());
  h.render(); return h;
}

test('gate never mounts protected content or logs out on outage; Retry restarts and deduplicates rapid clicks', async () => {
  const time = clock(); let calls = 0;
  requestSession = async () => { calls++; throw new ApiClientError('unavailable', 503); };
  const h = mountGate();
  try {
    assert.equal(h.tree.type, SessionStatusScreen);
    await time.advance(35000); h.render();
    assert.equal(h.tree.props.status, 'connection-failed'); assert.equal(calls, 8); assert.equal(logoutCalls, 0);
    let resolveRequest;
    requestSession = () => { calls++; return new Promise(resolve => { resolveRequest = resolve; }); };
    h.tree.props.onRetry(); h.tree.props.onRetry(); h.render();
    assert.equal(calls, 9); assert.equal(h.tree.type, SessionStatusScreen);
    resolveRequest({ data: { id: 'user-1', role: 'medico_veterinario', tenant_id: 'tenant-a' } }); await flush(); h.render();
    assert.equal(h.tree.props.children, 'protected application');
    assert.equal(h.tree.props.value.currentUser.tenant_id, 'tenant-a'); assert.equal(logoutCalls, 0);
  } finally { h.dispose(); time.restore(); }
});

test('gate cancellation suppresses retries and stale successful responses', async () => {
  const time = clock(); let resolveRequest, capturedSignal;
  requestSession = signal => { capturedSignal = signal; return new Promise(resolve => { resolveRequest = resolve; }); };
  const h = mountGate();
  try {
    h.dispose(); assert.ok(capturedSignal.aborted);
    resolveRequest({ data: { id: 'old-account' } }); await flush(); h.render();
    assert.equal(h.tree.type, SessionStatusScreen); await time.advance(60000); assert.equal(time.pending, 0);
  } finally { time.restore(); }
});

test('authorization failure stays blocked and preserves credentials until an explicit login action', async () => {
  requestSession = async () => { throw new ApiClientError('forbidden', 403, 'inactive_user'); };
  const h = mountGate(); await flush(); h.render();
  assert.equal(h.tree.type, SessionStatusScreen); assert.equal(h.tree.props.status, 'authorization-failed'); assert.equal(logoutCalls, 0);
  h.tree.props.onLogin(); assert.equal(logoutCalls, 1); h.dispose();
});

test('network failure during the single token refresh preserves session and can recover without another forced refresh', async () => {
  const time = clock(); let requests = 0, refreshes = 0;
  try {
    const run = start(async () => {
      if (++requests === 1) throw new ApiClientError('expired', 401, 'invalid_auth_token');
      return 'validated';
    }, async () => { refreshes++; throw { code: 'auth/network-request-failed' }; });
    await flush(); assert.ok(run.statuses.includes('waiting-for-server'));
    await time.advance(5000); assert.equal((await run.result).status, 'authenticated'); assert.equal(refreshes, 1);
  } finally { time.restore(); }
});
