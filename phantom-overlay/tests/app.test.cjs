const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '..', 'dist', 'app.js'), 'utf8');
function setup(invoke) {
  const elements = {};
  const document = {getElementById(id) { return elements[id] ||= {value:'',textContent:'',disabled:false,addEventListener(type,fn){this[type]=fn;}}; }};
  const window = invoke ? {__TAURI__:{core:{invoke}}} : {};
  vm.runInNewContext(script,{document,window});
  return id => document.getElementById(id);
}
test('blank input does not invoke backend',async()=>{
 let calls=0; const el=setup(async()=>{calls++;});
 await el('generate').click(); assert.equal(calls,0); assert.match(el('status').textContent,/instruction/);
});
test('explicit context and literal output, not HTML',async()=>{
 const el=setup(async(name,args)=>{assert.equal(name,'trigger_materialize');assert.equal(args.context,'Rewrite this');return '<script>bad()</script>';});
 el('context').value='Rewrite this'; await el('generate').click();
 assert.equal(el('result').value,'<script>bad()</script>'); assert.equal(el('generate').disabled,false);
});
test('discard prevents late results and concurrent requests',async()=>{
 let resolve,calls=0;const el=setup(()=>{calls++;return new Promise(r=>{resolve=r;});});
 el('context').value='Test';const pending=el('generate').click();
 await el('generate').click(); assert.equal(calls,1);
 el('cancel').click();resolve('must not appear');await pending;
 assert.equal(el('result').value,'');assert.equal(el('generate').disabled,false);
});
test('backend failure is actionable and resets button',async()=>{
 const el=setup(async()=>{throw Error('Ollama unavailable');});el('context').value='Test';await el('generate').click();
 assert.match(el('status').textContent,/Generation failed/);assert.equal(el('generate').disabled,false);
});
test('browser-only preview does not fake generation',async()=>{
 const el=setup();el('context').value='Test';await el('generate').click();assert.match(el('status').textContent,/desktop app/);
});

test('readiness displays exact tag and inventory as literal text', async()=>{
 const el=setup(async(name)=>{assert.equal(name,'model_readiness');return {ready:true,configured_model:'test:latest',message:'Installed, not benchmarked.',models:[{name:'<script>bad()</script>',size:1073741824}]};});
 await el('check-models').click();assert.match(el('model-status').textContent,/Installed: test:latest/);assert.equal(el('models').textContent,'<script>bad()</script> (1.00 GiB on disk)');assert.equal(el('check-models').disabled,false);
});
test('readiness error clears stale inventory and enables retry',async()=>{
 const el=setup(async()=>{throw Error('Runtime unavailable');});el('models').textContent='old';
 await el('check-models').click();assert.equal(el('models').textContent,'');assert.match(el('model-status').textContent,/Runtime unavailable/);assert.equal(el('check-models').disabled,false);
});
test('readiness serializes requests and never generates or downloads',async()=>{
 let resolve,calls=0;const el=setup((name)=>{assert.equal(name,'model_readiness');calls++;return new Promise(r=>resolve=r);});
 const pending=el('check-models').click();await el('check-models').click();assert.equal(calls,1);
 resolve({ready:false,configured_model:'missing',message:'Not installed.',models:[]});await pending;
 assert.match(el('model-status').textContent,/Not ready/);assert.match(el('models').textContent,/never downloads/);
});
