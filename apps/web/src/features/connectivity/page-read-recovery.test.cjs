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

require.extensions['.css'] = module => { module.exports = {}; };
const { PageReadRecovery } = require('./page-read-recovery.ts');
const { PageReadStatus } = require('./page-read-boundary.tsx');
const { api, ApiClientError, setAuthTokenProvider, setPageReadHandler, getApiErrorMessage } = require('../../lib/api.ts');
const { renderToStaticMarkup } = require('react-dom/server');
const React = require('react');
const flush = async () => { for (let i = 0; i < 40; i++) await Promise.resolve(); };

function clock() {
  let now = 0, id = 0; const tasks = new Map();
  const original = [global.setTimeout, global.clearTimeout, Date.now];
  Date.now = () => now;
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
    restore() { [global.setTimeout, global.clearTimeout, Date.now] = original; },
  };
}

const unavailable = () => new ApiClientError('Unavailable', 503, 'auth_verification_unavailable');
const html = state => renderToStaticMarkup(React.createElement(PageReadStatus, { state, retry() {} }));
function setup() {
  const time = clock(), manager = new PageReadRecovery(), states = [];
  manager.subscribe(state => states.push(state));
  return { time, manager, states, state: () => states.at(-1), cleanup() { manager.dispose(); time.restore(); } };
}

test('reactive countdown renders 5,4,3,2,1 and replays exactly once; success removes timers', async () => {
  const h = setup(); let calls = 0;
  try {
    const result = h.manager.run('/items?page=3', async () => { if (++calls === 1) throw unavailable(); return 'rows'; });
    await flush();
    for (const seconds of [5, 4, 3, 2, 1]) {
      assert.equal(h.state().seconds, seconds); assert.match(html(h.state()), new RegExp(`Reintento automático en ${seconds} s`));
      assert.equal(calls, 1); assert.equal(h.time.pending, 1); await h.time.advance(1000);
    }
    assert.equal(await result, 'rows'); assert.equal(calls, 2); assert.equal(h.state().phase, 'idle');
    assert.equal(h.time.pending, 0); assert.equal(html(h.state()), '');
  } finally { h.cleanup(); }
});

test('Recargar ahora cancels the old countdown, ignores duplicate clicks and stops counting during the request', async () => {
  const h = setup(); let calls = 0, release;
  try {
    const result = h.manager.run('/items', async () => { if (++calls === 1) throw unavailable(); return new Promise(resolve => { release = resolve; }); });
    await h.time.advance(2000);
    const retry = h.manager.retryNow(); void h.manager.retryNow(); await flush();
    assert.equal(calls, 2); assert.equal(h.state().phase, 'retrying'); assert.match(html(h.state()), /Reintentando/);
    await h.time.advance(5000); assert.equal(calls, 2); assert.equal(h.state().phase, 'retrying');
    release('rows'); await retry; assert.equal(await result, 'rows'); assert.equal(h.time.pending, 0);
  } finally { h.cleanup(); }
});

test('repeated failure restarts at five and stops at eight attempts; final Retry starts a fresh cycle', async () => {
  const h = setup(); let calls = 0, recovered = false;
  try {
    const result = h.manager.run('/items', async () => { calls++; if (!recovered) throw unavailable(); return 'rows'; });
    await h.time.advance(5000); assert.equal(calls, 2); assert.equal(h.state().seconds, 5);
    await h.time.advance(30000); assert.equal(calls, 8); assert.equal(h.state().phase, 'failed'); assert.equal(h.time.pending, 0);
    assert.match(html(h.state()), /No pudimos conectar con el servidor/); assert.match(html(h.state()), /Reintentar/);
    await h.time.advance(60000); assert.equal(calls, 8);
    recovered = true; await h.manager.retryNow(); assert.equal(await result, 'rows'); assert.equal(calls, 9); assert.equal(h.state().phase, 'idle');
  } finally { h.cleanup(); }
});

test('global deadline aborts a stuck request at forty seconds without overlapping attempts', async () => {
  const h = setup(); let calls = 0, aborted = false;
  const result = h.manager.run('/items', signal => new Promise((_, reject) => {
    calls++; signal.addEventListener('abort', () => { aborted = true; reject(signal.reason); }, { once: true });
  }));
  result.catch(() => {});
  try {
    await h.time.advance(40000); assert.ok(aborted); assert.equal(calls, 1); assert.equal(h.state().phase, 'failed'); assert.equal(h.time.pending, 0);
  } finally { h.cleanup(); }
});

test('navigation/unmount cancels countdown and active GET; late responses cannot update a new route', async () => {
  const h = setup(); let calls = 0;
  const result = h.manager.run('/old', async () => { calls++; throw unavailable(); });
  const rejected = assert.rejects(result, error => error.code === 'read_cancelled');
  await h.time.advance(1000); h.manager.dispose(); await rejected;
  const before = [...h.states]; await h.time.advance(10000);
  assert.equal(calls, 1); assert.deepEqual(h.states, before); assert.equal(h.time.pending, 0); h.time.restore();
  const next = setup(); let release, signal;
  const active = next.manager.run('/old', s => { signal = s; return new Promise(resolve => { release = resolve; }); });
  const activeRejected = assert.rejects(active); next.manager.dispose(); release('late'); await activeRejected; await flush();
  assert.ok(signal.aborted); assert.equal(next.state().phase, 'idle'); next.time.restore();
});

test('duplicate GETs share one load and multiple failed reads share one countdown with sequential retries', async () => {
  const h = setup(); let a = 0, b = 0, active = 0, max = 0;
  const read = key => async () => {
    const calls = key === 'a' ? ++a : ++b;
    if (calls === 1) throw unavailable();
    active++; max = Math.max(max, active); await Promise.resolve(); active--; return key;
  };
  try {
    const one = h.manager.run('/a', read('a'));
    const duplicate = h.manager.run('/a', () => assert.fail('duplicate GET'));
    const two = h.manager.run('/b', read('b'));
    assert.equal(one, duplicate); await flush(); assert.equal(h.time.pending, 1);
    await h.time.advance(5000); assert.deepEqual(await Promise.all([one, two]), ['a', 'b']);
    assert.equal(max, 1); assert.equal(a, 2); assert.equal(b, 2); assert.equal(h.time.pending, 0);
  } finally { h.cleanup(); }
});

test('401,403,404,422 and permanent 501 errors keep their existing classification, without connectivity retries', async () => {
  for (const status of [401, 403, 404, 422, 501]) {
    const h = setup(); let calls = 0;
    const error = new ApiClientError('original', status, status === 401 ? 'invalid_auth_token' : 'validation_error');
    try {
      await assert.rejects(h.manager.run('/items', async () => { calls++; throw error; }), e => e === error);
      await h.time.advance(50000); assert.equal(calls, 1); assert.equal(h.state().phase, 'idle');
      if (status === 401) assert.match(getApiErrorMessage(error), /sesión expiró/);
    } finally { h.cleanup(); }
  }
});

test('HTTP integration retries the exact authenticated GET and never refreshes the route or replays mutations', async () => {
  const h = setup(), oldFetch = global.fetch; const unregister = setPageReadHandler(h.manager.run);
  let requests = [], recovered = false;
  setAuthTokenProvider(async () => 'existing-token');
  global.fetch = async (url, init) => {
    requests.push({ url, method: init.method }); assert.equal(init.headers.get('Authorization'), 'Bearer existing-token');
    if (!recovered) throw new TypeError('offline');
    return new Response(JSON.stringify({ data: ['rows'] }));
  };
  try {
    const result = api.get('/api/v1/inventory/items?search=cat&page=3&sort_direction=desc');
    await flush(); assert.equal(requests.length, 1); assert.equal(h.state().seconds, 5);
    for (const mutate of [() => api.post('/sale', {}), () => api.patch('/sale', {}), () => api.delete('/sale'), () => api.postFormData('/file', new FormData()), () => api.postBlob('/export', {})]) await assert.rejects(mutate());
    assert.equal(requests.length, 6); recovered = true; await h.time.advance(5000);
    assert.deepEqual(await result, { data: ['rows'] }); assert.equal(requests.length, 7); assert.equal(requests[0].url, requests.at(-1).url);
  } finally { unregister(); h.cleanup(); global.fetch = oldFetch; setAuthTokenProvider(null); }
});

test('bootstrap explicit retry opt-out bypasses page recovery', async () => {
  const h = setup(), oldFetch = global.fetch; const unregister = setPageReadHandler(h.manager.run); let calls = 0;
  setAuthTokenProvider(async () => 'token'); global.fetch = async () => { calls++; return new Response('{}', { status: 503 }); };
  try {
    await assert.rejects(api.get('/api/v1/auth/me', { retryTransient: false, signal: new AbortController().signal }));
    assert.equal(calls, 1); assert.equal(h.state().phase, 'idle'); assert.equal(h.time.pending, 0);
  } finally { unregister(); h.cleanup(); global.fetch = oldFetch; setAuthTokenProvider(null); }
});
