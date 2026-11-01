const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../dist/app.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));
const ready = {ready:true, configured_model:'fixture', expected_digest:'a'.repeat(64), identity_check_scope:'reported-only', installed_models:[]};
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}
function fixture() {
  const elements = new Map(), calls = [], checks = [], runs = [], cancels = [];
  const document = {getElementById(id) {
    if (!elements.has(id)) elements.set(id, {
      value:'', textContent:'', disabled:false, listeners:new Map(),
      addEventListener(type, callback) {
        const listeners = this.listeners.get(type) || [];
        listeners.push(callback); this.listeners.set(type, listeners);
      },
      async emit(type) {
        // DOM dispatch does not wait for async handlers to settle.
        for (const callback of this.listeners.get(type) || []) callback({type, target:this});
        await tick();
      }
    });
    return elements.get(id);
  }};
  const window = {__TAURI__:{core:{invoke(name, args) {
    calls.push({name, args});
    const d = deferred();
    if (name === 'model_readiness') checks.push(d);
    else if (name === 'trigger_materialize') runs.push(d);
    else if (name === 'cancel_materialize') cancels.push(d);
    else throw Error(`Unexpected IPC: ${name}`);
    return d.promise;
  }}}};
  vm.runInNewContext(source, {document, window});
  return {el:id => document.getElementById(id), calls, checks, runs, cancels,
    async enable() { checks[0].resolve(ready); await tick(); },
    async probe() { await document.getElementById('retry-model').emit('click'); return checks.at(-1); },
    async generate() { await document.getElementById('generate').emit('click'); }
  };
}
async function started() {
  const a = fixture(); await a.enable();
  a.el('context').value = 'Explicit fixture'; await a.generate();
  assert.equal(a.runs.length, 1, 'One admitted generation');
  return a;
}
function needsRecheck(a) {
  assert.match(a.el('model-status').textContent, /needs?[^\n]*recheck|recheck[^\n]*required/i, 'Explicit needs-recheck model status');
  assert.equal(a.el('generate').disabled, true, 'Failure closes readiness gate');
  assert.equal(a.el('result').value, '', 'Failure exposes no output');
}
async function blocked(a) {
  const count = a.runs.length;
  await a.generate();
  assert.equal(a.runs.length, count, 'Handler admission gate, not merely disabled styling');
}
async function restore(a) {
  const check = await a.probe(); check.resolve(ready); await tick();
  assert.match(a.el('model-status').textContent, /Ready: fixture/);
  assert.equal(a.el('generate').disabled, false);
}
function settleCancel(a, outcome) {
  if (outcome === 'rejected') a.cancels[0].reject(Error('cancel IPC lost'));
  else a.cancels[0].resolve(outcome === 'accepted');
}
function cancellationDiagnostic(a, action, outcome) {
  const status = a.el('status').textContent;
  assert.match(status, /discard/i);
  if (action === 'input') assert.match(status, /input changed/i);
  assert.match(status, outcome === 'accepted' ? /cancellation requested/i : outcome === 'false' ? /no active request acknowledged/i : /could not be confirmed/i);
  assert.doesNotMatch(status, /generation failed|was stopped|has been stopped/i);
}

test('readiness failure: current rejection closes gate without automatic readiness IPC; explicit retry restores', async () => {
  const a = await started(); a.runs[0].reject(Error('runtime unavailable')); await tick();
  assert.match(a.el('status').textContent, /Generation failed:.*runtime unavailable/);
  needsRecheck(a); await blocked(a);
  assert.equal(a.checks.length, 1, 'No automatic readiness IPC on rejection or blocked generation');
  await restore(a);
  assert.equal(a.checks.length, 2);
  await a.generate(); assert.equal(a.runs.length, 2);
  a.runs[1].resolve('Recovered preview'); await tick();
  assert.equal(a.el('result').value, 'Recovered preview');
});

for (const outcome of ['success', 'failure']) {
  test(`readiness failure: ALL pre-failure unresolved probes are stale (${outcome}), even after fresh recovery`, async () => {
    const a = await started();
    const old = await a.probe(), newer = await a.probe();
    a.runs[0].reject(Error('generation broke')); await tick();
    needsRecheck(a);
    const failureStatus = a.el('model-status').textContent;
    if (outcome === 'success') newer.resolve({...ready, configured_model:'stale-newer'});
    else newer.reject(Error('obsolete readiness failure'));
    await tick();
    assert.equal(a.el('model-status').textContent, failureStatus);
    assert.equal(a.el('generate').disabled, true);
    await blocked(a);
    assert.equal(a.checks.length, 3, 'No automatic readiness IPC');
    await restore(a);
    const recovered = a.el('model-status').textContent;
    if (outcome === 'success') old.resolve({...ready, configured_model:'stale-oldest'});
    else old.reject(Error('obsolete oldest failure'));
    await tick();
    assert.equal(a.el('model-status').textContent, recovered);
    assert.equal(a.el('generate').disabled, false);
    assert.equal(a.checks.length, 4);
  });
}

test('readiness failure: newer successful probe completed BEFORE rejection is invalidated', async () => {
  const a = await started(); const check = await a.probe();
  check.resolve({...ready, configured_model:'newer'}); await tick();
  assert.match(a.el('model-status').textContent, /Ready: newer/);
  assert.equal(a.el('generate').disabled, true, 'Pending generation still gates admission');
  await blocked(a);
  a.runs[0].reject(Error('runtime failed later')); await tick();
  needsRecheck(a); await blocked(a);
  assert.equal(a.checks.length, 2);
  await restore(a);
});

test('readiness failure: every admitted rejection invalidates a freshly recovered snapshot', async () => {
  const a = await started();
  for (let i = 0; i < 2; i++) {
    a.runs[i].reject(Error(`failure ${i}`)); await tick();
    needsRecheck(a); await blocked(a);
    assert.equal(a.checks.length, i + 1);
    await restore(a);
    if (i === 0) { await a.generate(); assert.equal(a.runs.length, 2); }
  }
});

test('readiness failure: plain success preserves readiness, literal preview and IPC count', async () => {
  const a = await started();
  a.runs[0].resolve('<script>literal preview</script>'); await tick();
  assert.equal(a.el('result').value, '<script>literal preview</script>');
  assert.match(a.el('status').textContent, /Ready for your review/);
  assert.match(a.el('model-status').textContent, /Ready: fixture/);
  assert.equal(a.el('generate').disabled, false);
  assert.deepEqual(a.calls.map(c => c.name), ['model_readiness', 'trigger_materialize']);
});

for (const action of ['cancel', 'clear-session', 'input']) {
  for (const outcome of ['accepted', 'false', 'rejected']) {
    for (const order of ['ack-first', 'failure-first']) {
      test(`readiness failure after ${action}: ${outcome}, ${order} preserves diagnostics and cancellation ownership`, async () => {
        const a = await started();
        if (action === 'input') a.el('context').value = 'Changed fixture';
        await a.el(action === 'input' ? 'context' : action).emit(action === 'input' ? 'input' : 'click');
        assert.equal(a.cancels.length, 1);
        const requesting = a.el('status').textContent;
        assert.match(requesting, /Requesting cancellation/);
        if (order === 'ack-first') {
          settleCancel(a, outcome); await tick();
          cancellationDiagnostic(a, action, outcome);
          const pendingProbe = await a.probe(); pendingProbe.resolve(ready); await tick();
          assert.equal(a.el('generate').disabled, true, 'Fresh readiness cannot bypass pending request');
          await blocked(a);
        }
        const beforeFailure = a.el('status').textContent;
        a.runs[0].reject(Error('discarded request failed')); await tick();
        assert.equal(a.el('status').textContent, beforeFailure, 'Stale generation epoch cannot replace discard/cancel diagnostics');
        needsRecheck(a);
        assert.equal(a.checks.length, order === 'ack-first' ? 2 : 1, 'Rejection does not issue readiness IPC');
        if (order === 'failure-first') await blocked(a);
        const fresh = await a.probe();
        if (order === 'ack-first') {
          // Passive async updates preserve diagnostics. A deliberate synthetic click
          // on disabled Generate is a separate stimulus with its own instruction.
          cancellationDiagnostic(a, action, outcome);
          await blocked(a);
          assert.equal(a.el('status').textContent, action === 'clear-session'
            ? 'Add an instruction and text first.'
            : 'Wait for a successful local model readiness check.');
          assert.equal(a.checks.length, 3, 'Blocked admission does not issue readiness IPC');
        }
        fresh.resolve(ready); await tick();
        assert.match(a.el('model-status').textContent, /Ready: fixture/);
        if (order === 'failure-first') {
          assert.equal(a.el('generate').disabled, true, 'Fresh readiness cannot bypass pending cancellation');
          await blocked(a);
          assert.equal(a.el('status').textContent, requesting);
          settleCancel(a, outcome); await tick();
        }
        if (order === 'failure-first') cancellationDiagnostic(a, action, outcome);
        else assert.equal(a.el('status').textContent, action === 'clear-session'
          ? 'Add an instruction and text first.'
          : 'Wait for a successful local model readiness check.', 'Readiness completion preserves the explicit-click instruction');
        assert.equal(a.el('result').value, '');
        assert.equal(a.el('context').value, action === 'clear-session' ? '' : action === 'input' ? 'Changed fixture' : 'Explicit fixture');
        assert.equal(a.el('generate').disabled, false, 'Fresh check and settled ownership allow retry');
        assert.equal(a.cancels.length, 1);
        a.el('context').value = 'Fresh explicit input';
        await a.generate(); assert.equal(a.runs.length, 2);
        assert.equal(a.calls.filter(c => c.name === 'trigger_materialize')[1].args.context, 'Fresh explicit input');
        a.runs[1].resolve('Fresh preview'); await tick();
        assert.equal(a.el('result').value, 'Fresh preview');
      });
    }
  }
}

for (const order of ['ack-first', 'completion-first']) {
  test(`readiness failure regression: successful discarded request retains both cancellation gates (${order})`, async () => {
    const a = await started(); await a.el('cancel').emit('click');
    const check = await a.probe(); check.resolve(ready); await tick();
    assert.equal(a.el('generate').disabled, true); await blocked(a);
    if (order === 'ack-first') settleCancel(a, 'accepted');
    else a.runs[0].resolve('Discarded success');
    await tick();
    assert.equal(a.el('generate').disabled, true); await blocked(a);
    if (order === 'ack-first') a.runs[0].resolve('Discarded success');
    else settleCancel(a, 'accepted');
    await tick();
    assert.equal(a.el('result').value, '');
    assert.equal(a.el('generate').disabled, false);
    assert.match(a.el('model-status').textContent, /Ready: fixture/);
    cancellationDiagnostic(a, 'cancel', 'accepted');
    assert.deepEqual(a.calls.map(c => c.name), ['model_readiness', 'trigger_materialize', 'cancel_materialize', 'model_readiness']);
  });
}
