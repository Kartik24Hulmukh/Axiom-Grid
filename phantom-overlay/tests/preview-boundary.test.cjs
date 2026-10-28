const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'dist/app.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));

function app(cancel = () => Promise.resolve(true)) {
  const elements = new Map();
  const calls = [];
  let finish;
  const document = {getElementById(id) {
    if (!elements.has(id)) elements.set(id, {value:'', disabled:false, textContent:'', addEventListener(type, fn) { this[type] = fn; }});
    return elements.get(id);
  }};
  Object.defineProperty(document, 'activeElement', {get() {throw Error('outside-field capture forbidden');}});
  const window = {__TAURI__:{core:{invoke(name, args) {
    calls.push({name, args});
    if (name === 'model_readiness') return Promise.resolve({ready:true, configured_model:'fixture', expected_digest:'a'.repeat(64), identity_check_scope:'reported-only', installed_models:[]});
    if (name === 'trigger_materialize') return new Promise(resolve => { finish = resolve; });
    if (name === 'cancel_materialize') return cancel();
    throw Error(`unapproved command ${name}`);
  }}}};
  for (const name of ['navigator','localStorage','sessionStorage']) {
    Object.defineProperty(window, name, {get() {throw Error(`${name} forbidden`);}});
  }
  vm.runInNewContext(source, {document,window});
  return {el:document.getElementById, calls, finish(value) { finish(value); }};
}

test('preview uses only readiness, explicit generation and cancellation IPC', () => {
  const invoked = [...source.matchAll(/\.invoke\("([^"]+)"/g)].map(x=>x[1]).sort();
  assert.deepEqual(invoked, ['cancel_materialize','model_readiness','trigger_materialize']);
  assert.doesNotMatch(source, /clipboard|localStorage|sessionStorage|activeElement|innerHTML|execCommand|fetch\s*\(|WebSocket/);
});

test('native capabilities do not grant shell, filesystem, screen or clipboard access', () => {
  const capabilities = JSON.parse(fs.readFileSync(path.join(root,'src-tauri/capabilities/default.json'),'utf8'));
  assert.deepEqual(capabilities.permissions, ['core:default']);
  const backend = fs.readFileSync(path.join(root,'src-tauri/src/lib.rs'),'utf8');
  const registered = backend.match(/generate_handler!\[([\s\S]*?)\]/)[1].split(',').map(x=>x.trim()).filter(Boolean).sort();
  assert.deepEqual(registered, ['cancel_materialize','model_readiness','toggle_visibility','trigger_materialize']);
});

test('desktop preview is visible in taskbar and not a topmost covert overlay', () => {
  const config = JSON.parse(fs.readFileSync(path.join(root,'src-tauri/tauri.conf.json'),'utf8'));
  assert.equal(config.app.windows[0].skipTaskbar, false);
  assert.equal(config.app.windows[0].alwaysOnTop, false);
  assert.equal(config.app.windows[0].focus, true);
  assert.equal(config.bundle.active, false); // no qualified installer is claimed
});

test('clear session empties explicit input and output without invoking generation', async () => {
  const a=app(); await tick(); a.el('context').value='private input'; a.el('result').value='private output';
  await a.el('clear-session').click();
  assert.equal(a.el('context').value,''); assert.equal(a.el('result').value,'');
  assert.deepEqual(a.calls.map(x=>x.name), ['model_readiness']);
});

test('clear during generation cancels and rejects late result without capture APIs', async () => {
  const a=app(); await tick(); a.el('context').value='explicit fixture';
  const run=a.el('generate').click(); await a.el('clear-session').click();
  assert.equal(a.el('context').value,''); assert.equal(a.el('result').value,'');
  assert.equal(a.calls[1].args.context,'explicit fixture');
  a.finish('must not reappear'); await run;
  assert.equal(a.el('result').value,'');
  assert.deepEqual(a.calls.map(x=>x.name), ['model_readiness','trigger_materialize','cancel_materialize']);
});

test('UI documents manual copying, authorized scope and reset limitations', () => {
  const html=fs.readFileSync(path.join(root,'dist/index.html'),'utf8');
  assert.match(html,/Automatic insertion is disabled/);
  assert.match(html,/Authorized devices and permitted tasks only/);
  assert.match(html,/backend and OS retention are not certified/);
  assert.match(html,/Windows currently requires an explicitly configured token/);
  assert.doesNotMatch(html,/pairs automatically/);
});

test('clear still clears input while cancellation acknowledgement is pending', async () => {
  let acknowledge; const a=app(()=>new Promise(resolve=>{acknowledge=resolve;}));
  await tick(); a.el('context').value='private input'; const run=a.el('generate').click();
  const cancel=a.el('cancel').click();
  await a.el('clear-session').click();
  assert.equal(a.el('context').value,''); assert.equal(a.el('result').value,'');
  a.finish('late'); await run; acknowledge(true); await cancel;
  assert.equal(a.el('result').value,'');
});
