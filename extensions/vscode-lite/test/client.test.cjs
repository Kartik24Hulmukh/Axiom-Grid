'use strict';

// Deliberately no listening socket: every attempted HTTP request is intercepted.
const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { EventEmitter } = require('node:events');
const TOKEN = 'aB09'.repeat(16);
const LIMIT = 256 * 1024;
const MODEL = Object.freeze({ name: 'fixture:latest', size: 1, digest: 'a'.repeat(64) });
const READY = Object.freeze({ ready: true, configured_model: MODEL.name,
  expected_digest: MODEL.digest, identity_check_scope: 'reported-only', installed_models: [MODEL] });

function response(status, chunks, headers = {}) {
  const res = new EventEmitter();
  Object.assign(res, { statusCode: status, headers, complete: true, destroyed: false, resumed: false });
  res.destroy = () => { res.destroyed = true; return res; };
  res.resume = () => { res.resumed = true; return res; };
  res.setEncoding = () => { throw new Error('Strict UTF-8 requires byte decoding'); };
  res.deliver = () => {
    for (const chunk of chunks) if (!res.destroyed) res.emit('data', chunk);
    if (!res.destroyed) res.emit('end');
  };
  return res;
}
const json = value => Buffer.from(JSON.stringify(value));

function transport(plan = {}) {
  const calls = [];
  function request(...args) {
    let options = args[0];
    if (typeof options === 'string' || options instanceof URL) {
      const url = new URL(options);
      options = { protocol: url.protocol, hostname: url.hostname, port: url.port,
        path: url.pathname + url.search, ...(typeof args[1] === 'object' ? args[1] : {}) };
    }
    const cb = args.find(x => typeof x === 'function');
    const req = new EventEmitter();
    const socket = new EventEmitter();
    Object.assign(socket, { connecting: true, destroyed: false });
    socket.setTimeout = ms => { socket.timeout = ms; return socket; };
    socket.setNoDelay = () => socket;
    socket.setKeepAlive = () => socket;
    socket.destroy = () => { socket.destroyed = true; return socket; };
    Object.assign(req, { options, socket, chunks: [], destroyed: false, ended: false });
    req.setTimeout = (ms, fn) => { req.timeout = ms; if (fn) req.on('timeout', fn); return req; };
    req.setHeader = (key, value) => { (options.headers ||= {})[key] = value; };
    req.getHeader = key => Object.entries(options.headers || {}).find(([k]) => k.toLowerCase() === key.toLowerCase())?.[1];
    req.write = chunk => { req.chunks.push(Buffer.from(chunk)); return true; };
    req.destroy = error => {
      if (req.destroyed) return req;
      req.destroyed = true; socket.destroy();
      queueMicrotask(() => { if (error) req.emit('error', error); req.emit('close'); });
      return req;
    };
    req.abort = () => req.destroy();
    if (cb) req.on('response', cb);
    req.end = chunk => {
      if (chunk !== undefined) req.write(chunk);
      req.ended = true;
      queueMicrotask(() => {
        if (req.destroyed) return;
        req.emit('socket', socket);
        if (plan.connect !== false) { socket.connecting = false; socket.emit('connect'); }
        if (plan.onEnd) plan.onEnd(req);
        if (plan.error) { req.emit('error', plan.error); return; }
        if (plan.res && !req.destroyed) {
          req.emit('response', plan.res);
          if (plan.deliver !== false) plan.res.deliver();
        }
      });
      return req;
    };
    calls.push(req);
    return req;
  }
  return { request, calls };
}

function assertFixed(req, method, path) {
  const o = req.options;
  assert.equal(o.hostname || o.host, '127.0.0.1');
  assert.equal(Number(o.port), 7437);
  assert.equal(o.method || 'GET', method);
  assert.equal(o.path, path);
  assert.equal(o.agent, false);
  const headers = Object.fromEntries(Object.entries(o.headers || {}).map(([k, v]) => [k.toLowerCase(), v]));
  assert.equal(headers.authorization, `Bearer ${TOKEN}`);
  assert.equal(headers['proxy-authorization'], undefined);
  assert.ok(!String(o.path).includes(TOKEN));
  assert.ok(!String(o.hostname || o.host).includes(TOKEN));
  return headers;
}

// One sequential parent keeps the process-wide http.request monkeypatch isolated.
test('client security contract (mock HTTP only)', async t => {
  const original = http.request;
  let active = transport();
  http.request = (...args) => active.request(...args);
  t.after(() => { http.request = original; });
  const { readiness, generate, validateToken, ClientError } = require('../client.js');
  function use(plan) { active = transport(plan); return active; }
  const staticMessages = new Map();
  async function rejected(action, code, forbidden = []) {
    await assert.rejects(async () => action(), error => {
      assert.ok(error instanceof ClientError);
      if (code) assert.equal(error.code, code);
      assert.equal(typeof error.message, 'string');
      assert.ok(error.message.length > 0 && error.message.length < 240);
      if (staticMessages.has(error.code)) assert.equal(error.message, staticMessages.get(error.code));
      else staticMessages.set(error.code, error.message);
      const exposed = `${error.stack}\n${error.message}\n${JSON.stringify(error, Object.getOwnPropertyNames(error))}`;
      for (const secret of [TOKEN, 'PRIVATE_SOURCE_9182', 'OS_SECRET_4482', ...forbidden]) {
        assert.ok(!exposed.includes(secret), `sanitized error must not contain ${secret}`);
      }
      return true;
    });
  }

  await t.test('exact ASCII hex token validation; no coercion or trimming', async () => {
    assert.equal(validateToken(TOKEN), true);
    assert.equal(validateToken('F'.repeat(64)), true);
    for (const token of [undefined, null, {}, 123, '', 'a'.repeat(63), 'a'.repeat(65),
      'g'.repeat(64), ' '.repeat(64), ` ${TOKEN}`, `${TOKEN}\n`, 'Ａ'.repeat(64), new String(TOKEN)]) {
      assert.equal(validateToken(token), false);
      const mock = use({});
      await rejected(() => readiness(token), 'INVALID_TOKEN');
      await rejected(() => generate(token, 'PRIVATE_SOURCE_9182'), 'INVALID_TOKEN');
      assert.equal(mock.calls.length, 0);
    }
  });

  await t.test('invalid context never reaches HTTP', async () => {
    for (const context of [undefined, null, {}, [], 42, '', 'x'.repeat(16001), '😀'.repeat(16001), '\ud800', '\udfff', 'x\ud800y']) {
      const mock = use({});
      await rejected(() => generate(TOKEN, context), 'INVALID_CONTEXT');
      assert.equal(mock.calls.length, 0);
    }
  });

  await t.test('readiness fixed destination, bearer auth and metadata allowlist', async () => {
    const mock = use({ res: response(200, [json({ ...READY,
      installed_models: [{ ...MODEL, source: 'PRIVATE_SOURCE_9182', token: TOKEN }],
      source: 'PRIVATE_SOURCE_9182', token: TOKEN })]) });
    const result = await readiness(TOKEN);
    assertFixed(mock.calls[0], 'GET', '/readiness');
    assert.equal(mock.calls.length, 1);
    assert.equal(mock.calls[0].chunks.length, 0);
    assert.deepEqual(result, { ready: true, configured_model: READY.configured_model,
      expected_digest: READY.expected_digest, identity_check_scope: 'reported-only', installed_model_count: 1 });
    assert.ok(!JSON.stringify(result).includes('PRIVATE_SOURCE_9182'));
    assert.ok(!JSON.stringify(result).includes(TOKEN));
  });

  await t.test('generation serializes exact JSON context and counts Unicode scalars', async () => {
    for (const context of ['x', 'quotes " slash \\ CR\r LF\n tab\t 😀 PRIVATE_SOURCE_9182', '😀'.repeat(16000)]) {
      const suggestion = '😀'.repeat(4096);
      const mock = use({ res: response(200, [json({ suggestion })]) });
      assert.equal(await generate(TOKEN, context), suggestion);
      const headers = assertFixed(mock.calls[0], 'POST', '/materialize');
      assert.match(headers['content-type'], /^application\/json(?:\s*;.*)?$/i);
      assert.deepEqual(JSON.parse(Buffer.concat(mock.calls[0].chunks).toString('utf8')), { context, mode: 'code' });
      assert.equal(mock.calls.length, 1);
    }
  });

  await t.test('HTTP non-success never subscribes to or drains bodies; no redirects', async () => {
    for (const status of [300, 301, 302, 303, 307, 308, 400, 401, 403, 429, 500, 502, 503]) {
      for (const operation of [() => readiness(TOKEN), () => generate(TOKEN, 'PRIVATE_SOURCE_9182')]) {
        const res = response(status, [json({ ...READY, suggestion: 'plausible', error: TOKEN })], { location: 'http://attacker.invalid/' });
        const mock = use({ res, deliver: false });
        const expected = ({ 401: 'HTTP_UNAUTHORIZED', 429: 'HTTP_BUSY',
          502: 'HTTP_BACKEND_ERROR', 503: 'HTTP_UNAVAILABLE' })[status] || 'HTTP_ERROR';
        await rejected(operation, expected);
        assert.equal(mock.calls.length, 1);
        assert.equal(res.listenerCount('data'), 0);
        assert.equal(res.resumed, false);
      }
    }
  });

  await t.test('readiness requires literal boolean true', async () => {
    for (const ready of [false, 'true', 1, null, undefined]) {
      use({ res: response(200, [json({ ...READY, ready })]) });
      await rejected(() => readiness(TOKEN), ready === false ? 'NOT_READY' : 'INVALID_RESPONSE');
    }
  });

  await t.test('not-ready inventory can omit or mismatch the selected model', async () => {
    for (const installed_models of [[], [{ ...MODEL, digest: 'b'.repeat(64) }],
      [{ ...MODEL, size: 0 }], [MODEL, MODEL]]) {
      use({ res: response(200, [json({ ...READY, ready: false, installed_models })]) });
      await rejected(() => readiness(TOKEN), 'NOT_READY');
      use({ res: response(200, [json({ ...READY, ready: true, installed_models })]) });
      await rejected(() => readiness(TOKEN), 'INVALID_RESPONSE');
    }
    use({ res: response(200, [json({ ...READY, ready: false, installed_models: [null] })]) });
    await rejected(() => readiness(TOKEN), 'INVALID_RESPONSE');
  });

  await t.test('malformed JSON / strict UTF-8 reject for both endpoints', async () => {
    for (const bytes of [Buffer.from(''), Buffer.from('{'), Buffer.from('null'), Buffer.from('[]'), Buffer.from('"hello"'),
      Buffer.concat([Buffer.from('{"suggestion":"'), Buffer.from([0xc0, 0xaf]), Buffer.from('"}')]),
      Buffer.concat([Buffer.from('{"suggestion":"'), Buffer.from([0xed, 0xa0, 0x80]), Buffer.from('"}')]),
      Buffer.concat([Buffer.from('{"suggestion":"'), Buffer.from([0xf4, 0x90, 0x80, 0x80]), Buffer.from('"}')])]) {
      for (const operation of [() => readiness(TOKEN), () => generate(TOKEN, 'PRIVATE_SOURCE_9182')]) {
        use({ res: response(200, [bytes]) });
        await rejected(operation, 'INVALID_RESPONSE');
      }
    }
    const body = json({ suggestion: 'left😀right' });
    const split = body.indexOf(Buffer.from('😀')) + 2;
    use({ res: response(200, [body.subarray(0, split), body.subarray(split)]) });
    assert.equal(await generate(TOKEN, 'x'), 'left😀right');
  });

  await t.test('decoded body size enforced for chunking and stale content-length', async () => {
    for (const headers of [{}, { 'content-length': '1' }, { 'transfer-encoding': 'chunked' }]) {
      const bytes = json({ suggestion: 'ok', padding: 'x'.repeat(LIMIT) });
      for (const operation of [() => readiness(TOKEN), () => generate(TOKEN, 'PRIVATE_SOURCE_9182')]) {
        const res = response(200, [bytes.subarray(0, 100), bytes.subarray(100)], headers);
        const mock = use({ res });
        await rejected(operation, 'RESPONSE_TOO_LARGE');
        assert.ok(res.destroyed || mock.calls[0].destroyed || mock.calls[0].socket.destroyed);
      }
    }
    const prefix = Buffer.byteLength(JSON.stringify({ suggestion: 'ok', padding: '' }));
    const bytes = json({ suggestion: 'ok', padding: 'x'.repeat(LIMIT - prefix) });
    assert.equal(bytes.length, LIMIT);
    use({ res: response(200, [bytes]) });
    assert.equal(await generate(TOKEN, 'x'), 'ok');
  });

  await t.test('suggestion is bounded scalar string without forbidden control/bidi', async () => {
    const bad = [undefined, null, false, 7, {}, [], '', ' ', '\t\n\r', '\u00a0\u2003', 'x'.repeat(4097), '😀'.repeat(4097), '\ud800', '\udfff'];
    for (let i = 0; i < 32; i++) if (![9, 10, 13].includes(i)) bad.push(`x${String.fromCharCode(i)}y`);
    bad.push('x\x7fy');
    for (const [lo, hi] of [[0x202a, 0x202e], [0x2066, 0x2069]]) {
      for (let i = lo; i <= hi; i++) bad.push(`x${String.fromCodePoint(i)}y`);
    }
    for (const suggestion of bad) {
      use({ res: response(200, [json({ suggestion })]) });
      await rejected(() => generate(TOKEN, 'PRIVATE_SOURCE_9182'), 'INVALID_RESPONSE');
    }
    for (const suggestion of ['x\t\n\ry', 'é\u0301😀', 'x'.repeat(4096)]) {
      use({ res: response(200, [json({ suggestion })]) });
      assert.equal(await generate(TOKEN, 'x'), suggestion);
    }
  });

  await t.test('abort before send makes no request; in-flight abort destroys request; no /cancel', async () => {
    for (const fn of [signal => readiness(TOKEN, { signal }), signal => generate(TOKEN, 'PRIVATE_SOURCE_9182', { signal })]) {
      const before = new AbortController(); before.abort(new Error('OS_SECRET_4482'));
      let mock = use({});
      await rejected(() => fn(before.signal), 'ABORTED');
      assert.equal(mock.calls.length, 0);
      const during = new AbortController();
      mock = use({ onEnd: () => during.abort(new Error('OS_SECRET_4482')) });
      await rejected(() => fn(during.signal), 'ABORTED');
      assert.equal(mock.calls.length, 1);
      assert.equal(mock.calls[0].destroyed, true);
      assert.ok(mock.calls.every(req => req.options.path !== '/cancel'));
    }
  });

  await t.test('invalid AbortSignal never reaches HTTP', async () => {
    for (const signal of [null, false, 'signal', {}, { aborted: false, addEventListener() {} }]) {
      const mock = use({});
      await rejected(() => readiness(TOKEN, { signal }), 'INVALID_SIGNAL');
      await rejected(() => generate(TOKEN, 'x', { signal }), 'INVALID_SIGNAL');
      assert.equal(mock.calls.length, 0);
    }
  });

  await t.test('readiness validates canonical identity field shapes', async () => {
    const mutations = [{ configured_model: '' }, { configured_model: 7 },
      { configured_model: 'bad\nmodel' }, { configured_model: 'x'.repeat(257) },
      { expected_digest: 'a'.repeat(63) }, { expected_digest: 'A'.repeat(64) },
      { identity_check_scope: 'verified' }, { installed_models: {} }];
    for (const mutation of mutations) {
      use({ res: response(200, [json({ ...READY, ...mutation })]) });
      await rejected(() => readiness(TOKEN), 'INVALID_RESPONSE');
    }
    for (const key of Object.keys(READY)) {
      const payload = { ...READY }; delete payload[key];
      use({ res: response(200, [json(payload)]) });
      await rejected(() => readiness(TOKEN), 'INVALID_RESPONSE');
    }
  });

  await t.test('installed model records must be well formed, including unselected entries', async () => {
    const malformed = [null, false, [], 'model', {},
      { ...MODEL, name: '' }, { ...MODEL, name: 1 },
      { ...MODEL, name: 'x'.repeat(257) }, { ...MODEL, name: 'contains space' },
      { ...MODEL, name: 'line\nbreak' }, { ...MODEL, name: 'é' }, { ...MODEL, name: 'x\x7f' },
      { ...MODEL, size: -1 }, { ...MODEL, size: 0.5 },
      { ...MODEL, size: Number.MAX_SAFE_INTEGER + 1 }, { ...MODEL, size: '1' },
      { ...MODEL, size: null }, { ...MODEL, digest: null },
      { ...MODEL, digest: 1 }, { ...MODEL, digest: 'x'.repeat(257) }];
    for (const key of ['name', 'size', 'digest']) {
      const entry = { ...MODEL }; delete entry[key]; malformed.push(entry);
    }
    for (const entry of malformed) {
      // Keeping a valid selected entry must not hide a malformed other entry.
      use({ res: response(200, [json({ ...READY, installed_models: [MODEL, entry] })]) });
      await rejected(() => readiness(TOKEN), 'INVALID_RESPONSE');
    }
  });

  await t.test('readiness requires one positive-size digest-matching selected model', async () => {
    const invalidLists = [[], null, [null], [MODEL, MODEL],
      [{ ...MODEL, name: 'different:latest' }], [{ ...MODEL, size: 0 }],
      [{ ...MODEL, digest: 'b'.repeat(64) }], [{ ...MODEL, digest: '' }],
      [{ ...MODEL, digest: MODEL.digest.toUpperCase() }]];
    for (const installed_models of invalidLists) {
      use({ res: response(200, [json({ ...READY, installed_models })]) });
      await rejected(() => readiness(TOKEN), 'INVALID_RESPONSE');
    }
    // Legitimate unrelated models may be unloaded and have a noncanonical digest.
    const installed_models = [MODEL, { name: 'x'.repeat(256), size: 0, digest: 'z'.repeat(256) },
      { name: 'other:latest', size: Number.MAX_SAFE_INTEGER, digest: '' }];
    use({ res: response(200, [json({ ...READY, installed_models })]) });
    assert.deepEqual(await readiness(TOKEN), { ready: true, configured_model: MODEL.name,
      expected_digest: MODEL.digest, identity_check_scope: 'reported-only', installed_model_count: 3 });
  });

  await t.test('proxy environment cannot alter fixed direct HTTP destination', async () => {
    const names = ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'];
    const old = names.map(key => process.env[key]);
    try {
      for (const key of names) process.env[key] = 'http://proxy-user:proxy-secret@attacker.invalid:9999';
      const mock = use({ res: response(200, [json(READY)]) });
      await readiness(TOKEN);
      assertFixed(mock.calls[0], 'GET', '/readiness');
      assert.equal(mock.calls.length, 1);
      assert.ok(!JSON.stringify(mock.calls[0].options).includes('proxy-secret'));
    } finally {
      names.forEach((key, i) => { if (old[i] === undefined) delete process.env[key]; else process.env[key] = old[i]; });
    }
  });

  await t.test('2s connect and 95s total deadlines, not reset by body activity', async () => {
    const originalSet = global.setTimeout;
    const originalClear = global.clearTimeout;
    let now = 0;
    const timers = new Map();
    const scheduled = [];
    global.setTimeout = (fn, delay, ...args) => {
      const handle = { unref() { return handle; } };
      timers.set(handle, { at: now + delay, fn: () => fn(...args) });
      scheduled.push(delay);
      return handle;
    };
    global.clearTimeout = handle => timers.delete(handle);
    const advance = ms => {
      now += ms;
      for (const [handle, timer] of [...timers]) {
        if (timers.has(handle) && timer.at <= now) { timers.delete(handle); timer.fn(); }
      }
    };
    try {
      for (const connected of [false, true]) {
        now = 0; scheduled.length = 0; timers.clear();
        const res = response(200, []);
        const mock = use({ connect: connected, res: connected ? res : undefined, deliver: false });
        const pending = generate(TOKEN, 'PRIVATE_SOURCE_9182');
        const checked = rejected(() => pending, 'TIMEOUT');
        await Promise.resolve();
        assert.ok(scheduled.includes(2000), 'must schedule a 2 second connect bound');
        assert.ok(scheduled.includes(95000), 'must schedule a 95 second total bound');
        if (connected) {
          advance(94000);
          assert.equal(mock.calls[0].destroyed, false);
          res.emit('data', Buffer.from('{"suggestion":"'));
          advance(999);
          assert.equal(mock.calls[0].destroyed, false);
          advance(1);
        } else {
          advance(1999);
          assert.equal(mock.calls[0].destroyed, false);
          advance(1);
        }
        await checked;
        assert.equal(mock.calls[0].destroyed, true);
        assert.equal(mock.calls.length, 1);
        assert.equal(timers.size, 0, 'deadline timers cleaned up after settlement');
      }
    } finally { global.setTimeout = originalSet; global.clearTimeout = originalClear; }
  });

  await t.test('network errors never expose OS text, auth or context', async () => {
    for (const operation of [() => readiness(TOKEN), () => generate(TOKEN, 'PRIVATE_SOURCE_9182')]) {
      use({ error: new Error(`OS_SECRET_4482 ${TOKEN} PRIVATE_SOURCE_9182`) });
      await rejected(operation, 'CONNECTION_ERROR');
    }
  });
});
