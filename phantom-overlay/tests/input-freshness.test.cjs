const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../dist/app.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}
const ready = {ready:true, configured_model:'fixture', expected_digest:'a'.repeat(64), identity_check_scope:'reported-only', installed_models:[]};
function fixture() {
  const elements = new Map(), calls = [], runs = [], cancels = [], checks = [];
  const document = {getElementById(id) {
    if (!elements.has(id)) elements.set(id, {
      value:'', textContent:'', disabled:false, listeners:new Map(),
      addEventListener(type, callback) {
        const list = this.listeners.get(type) || [];
        list.push(callback); this.listeners.set(type, list);
      },
      async emit(type) {
        // Match DOM dispatch: async handlers do not delay dispatch completion.
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
  for (const property of ['navigator','localStorage','sessionStorage']) {
    Object.defineProperty(window, property, {get() { throw Error(`Forbidden ${property}`); }});
  }
  Object.defineProperty(document, 'activeElement', {get() {throw Error('Outside-field capture forbidden');}});
  vm.runInNewContext(source, {window, document});
  return {el: id => document.getElementById(id), calls, runs, cancels, checks,
    async enable() { checks[0].resolve(ready); await tick(); },
    async edit(value) { document.getElementById('context').value = value; await document.getElementById('context').emit('input'); },
    async generate(value) { if (value !== undefined) document.getElementById('context').value = value; await document.getElementById('generate').emit('click'); }
  };
}
function changedStatus(a) {
  assert.match(a.el('status').textContent, /input changed/i);
  assert.match(a.el('status').textContent, /discard/i);
  assert.doesNotMatch(a.el('status').textContent, /backend (?:has )?stopped|generation (?:has been |was )?stopped|erased/i);
}

test('input freshness: idle edits preserve readiness instructions and make no additional IPC', async () => {
  const a=fixture();
  a.el('status').textContent='Start the local runtime, then retry the model check.';
  const original=a.el('status').textContent;
  await a.edit('Typed while checking');
  assert.equal(a.el('status').textContent, original);
  assert.deepEqual(a.calls.map(c=>c.name), ['model_readiness']);
  assert.equal(a.el('generate').disabled, true);
  await a.enable(); await a.edit('More typing');
  assert.equal(a.el('status').textContent, original);
  assert.deepEqual(a.calls.map(c=>c.name), ['model_readiness']);
});

test('input freshness: input after completed preview clears old output, retains input, and does not cancel', async () => {
  const a=fixture(); await a.enable(); await a.generate('A');
  a.runs[0].resolve('Suggestion A'); await tick();
  await a.edit('B');
  assert.equal(a.el('result').value,'');
  assert.equal(a.el('context').value,'B');
  assert.equal(a.cancels.length,0); changedStatus(a);
  assert.equal(a.el('generate').disabled,false);
});

test('input freshness: pending edit cancels once, suppresses old result and gates restart until acknowledgement', async () => {
  const a=fixture(); await a.enable(); await a.generate('A');
  await a.edit('B');
  assert.equal(a.cancels.length,1); changedStatus(a);
  await a.edit('C'); await a.edit('D');
  assert.equal(a.cancels.length,1);
  assert.equal(a.el('context').value,'D');
  a.runs[0].resolve('Old A'); await tick();
  assert.equal(a.el('result').value,'');
  assert.equal(a.el('generate').disabled,true);
  await a.generate(); assert.equal(a.runs.length,1);
  a.cancels[0].resolve(true); await tick();
  assert.equal(a.el('generate').disabled,false);
  await a.generate(); assert.equal(a.runs.length,2);
  assert.equal(a.calls.filter(c=>c.name==='trigger_materialize')[1].args.context,'D');
  a.runs[1].resolve('Fresh D'); await tick();
  assert.equal(a.el('result').value,'Fresh D');
});

for (const outcome of ['accepted','false','rejected']) {
  test(`input freshness: ${outcome} cancellation before old completion keeps admission and suppresses late output`, async () => {
    const a=fixture(); await a.enable(); await a.generate('A'); await a.edit('B');
    assert.equal(a.cancels.length,1);
    if (outcome==='rejected') a.cancels[0].reject(Error('IPC lost'));
    else a.cancels[0].resolve(outcome==='accepted');
    await tick();
    assert.equal(a.el('generate').disabled,true);
    await a.generate(); assert.equal(a.runs.length,1);
    a.runs[0].resolve('Late A'); await tick();
    assert.equal(a.el('result').value,'');
    assert.equal(a.el('context').value,'B');
    assert.equal(a.el('generate').disabled,false);
    await a.generate(); a.runs[1].resolve('Fresh B'); await tick(); await tick();
    assert.equal(a.el('result').value,'Fresh B');
    assert.match(a.el('status').textContent,/ready for your review/i);
    assert.equal(a.el('generate').disabled,false);
  });
}

test('input freshness: clear during edit cancellation still clears context and late output', async () => {
  const a=fixture(); await a.enable(); await a.generate('A'); await a.edit('B');
  assert.equal(a.cancels.length,1);
  await a.el('clear-session').emit('click');
  assert.equal(a.el('context').value,''); assert.equal(a.el('result').value,'');
  assert.equal(a.cancels.length,1);
  a.runs[0].resolve('Late A'); a.cancels[0].resolve(true); await tick();
  assert.equal(a.el('context').value,''); assert.equal(a.el('result').value,'');
});

test('input freshness: readiness failure remains fail-closed after edit cancellation settles', async () => {
  const a=fixture(); await a.enable(); await a.generate('A'); await a.edit('B');
  assert.equal(a.cancels.length,1);
  await a.el('retry-model').emit('click'); a.checks[1].reject(Error('offline')); await tick();
  a.cancels[0].resolve(false); a.runs[0].resolve('Late A'); await tick();
  assert.equal(a.el('result').value,'');
  assert.equal(a.el('generate').disabled,true);
  await a.generate(); assert.equal(a.runs.length,1);
  assert.match(a.el('model-status').textContent,/offline/);
});

for (const outcome of ['accepted','false','rejected']) {
  test(`input freshness: repeated edit after ${outcome} acknowledgement preserves single cancellation ownership`, async () => {
    const a=fixture(); await a.enable(); await a.generate('A'); await a.edit('B');
    assert.equal(a.cancels.length,1);
    if (outcome==='rejected') a.cancels[0].reject(Error('IPC lost'));
    else a.cancels[0].resolve(outcome==='accepted');
    await tick();
    const acknowledgedStatus=a.el('status').textContent;
    changedStatus(a);
    if (outcome==='accepted') assert.match(acknowledgedStatus,/cancellation requested/i);
    else if (outcome==='false') assert.match(acknowledgedStatus,/no active request acknowledged/i);
    else assert.match(acknowledgedStatus,/could not be confirmed/i);
    await a.edit('C'); await a.edit('D');
    assert.equal(a.cancels.length,1,'Settled acknowledgement must not permit duplicate cancellation of the same request');
    assert.equal(a.el('status').textContent,acknowledgedStatus,'Further edits must preserve cancellation outcome diagnostics');
    assert.equal(a.el('context').value,'D');
    assert.equal(a.el('result').value,'');
    assert.equal(a.el('generate').disabled,true);
    await a.generate(); assert.equal(a.runs.length,1);
    a.runs[0].resolve('Late A'); await tick();
    assert.equal(a.el('result').value,'');
    assert.equal(a.el('status').textContent,acknowledgedStatus);
    assert.equal(a.el('generate').disabled,false);
    await a.generate(); assert.equal(a.runs.length,2);
    assert.equal(a.calls.filter(c=>c.name==='trigger_materialize')[1].args.context,'D');
    a.runs[1].resolve('Fresh D'); await tick();
    assert.equal(a.el('result').value,'Fresh D');
  });
}
