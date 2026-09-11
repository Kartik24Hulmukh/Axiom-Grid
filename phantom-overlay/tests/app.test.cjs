const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '..', 'dist', 'app.js'), 'utf8');
function setup(invoke, readiness = () => Promise.resolve({ready:true,configured_model:'test:latest',installed_models:[{name:'test:latest'}]})) {
  const elements = {};
  const document = {getElementById(id) { return elements[id] ||= {value:'',textContent:'',disabled:false,addEventListener(type,fn){this[type]=fn;}}; }};
  const window = invoke ? {__TAURI__:{core:{invoke}}} : {};
  if(invoke){ const original=invoke; window.__TAURI__.core.invoke=(name,args)=> name==='model_readiness' ? readiness() : original(name,args); }
  vm.runInNewContext(script,{document,window});
  return id => document.getElementById(id);
}
test('blank input does not invoke backend',async()=>{
 let calls=0; const el=setup(async()=>{calls++;});
 await el('generate').click(); assert.equal(calls,0); assert.match(el('status').textContent,/instruction/);
});
test('explicit context and literal output, not HTML',async()=>{
 const el=setup(async(name,args)=>{assert.equal(name,'trigger_materialize');assert.equal(args.context,'Rewrite this');return '<script>bad()</script>';});
 await tick();el('context').value='Rewrite this'; await el('generate').click();
 assert.equal(el('result').value,'<script>bad()</script>'); assert.equal(el('generate').disabled,false);
});
test('discard prevents late results and concurrent requests',async()=>{
 let resolve,calls=0;const el=setup((name)=>{if(name==='cancel_materialize')return Promise.resolve(true);calls++;return new Promise(r=>{resolve=r;});});
 await tick();el('context').value='Test';const pending=el('generate').click();
 await el('generate').click(); assert.equal(calls,1);
 el('cancel').click();resolve('must not appear');await pending;
 assert.equal(el('result').value,'');assert.equal(el('generate').disabled,false);
});
test('backend failure is actionable and resets button',async()=>{
 const el=setup(async()=>{throw Error('Ollama unavailable');});await tick();el('context').value='Test';await el('generate').click();
 assert.match(el('status').textContent,/Generation failed/);assert.equal(el('generate').disabled,false);
});
test('browser-only preview does not fake generation',async()=>{
 const el=setup();await tick();el('context').value='Test';await el('generate').click();assert.match(el('status').textContent,/desktop app/);
});

test('readiness displays exact configured model and enables generation',async()=>{
 const el=setup(async()=> 'ok'); await new Promise(r=>setImmediate(r));
 assert.match(el('model-status').textContent,/Ready: test:latest/); assert.equal(el('generate').disabled,false);
});
test('browser readiness fails closed',async()=>{
 const el=setup(); await new Promise(r=>setImmediate(r));
 assert.match(el('model-status').textContent,/Desktop runtime required/);
});

test('cancel while pending propagates to the backend',async()=>{
 let resolve,cancelCalls=0;const el=setup((name)=>{if(name==='cancel_materialize'){cancelCalls++;return Promise.resolve(true);}return new Promise(r=>{resolve=r;});});
 await tick();el('context').value='Test';const pendingRun=el('generate').click();
 el('cancel').click(); assert.equal(cancelCalls,1); assert.match(el('status').textContent,/Requesting cancellation/);
 resolve('late result'); await pendingRun; assert.equal(el('result').value,'');
});
test('cancel without pending work does not call the backend',async()=>{
 let cancelCalls=0;const el=setup((name)=>{if(name==='cancel_materialize'){cancelCalls++;}return Promise.resolve('x');});
 el('cancel').click(); assert.equal(cancelCalls,0); assert.match(el('status').textContent,/discarded/i);
});

const tick = () => new Promise(resolve => setImmediate(resolve));
test('browser readiness disables generation', async () => {
 const el=setup(); await tick(); assert.equal(el('generate').disabled,true);
});
test('generation cannot start before readiness resolves', async () => {
 let calls=0, ready; const el=setup(async()=>{calls++;},()=>new Promise(r=>{ready=r;}));
 await tick();el('context').value='Test'; await el('generate').click();
 assert.equal(calls,0); assert.equal(el('generate').disabled,true);
 ready({ready:true,configured_model:'test',installed_models:[]}); await tick();
 assert.equal(el('generate').disabled,false);
});
test('stale readiness cannot overwrite a newer failure', async () => {
 const checks=[];const el=setup(async()=>'',()=>new Promise((resolve,reject)=>checks.push({resolve,reject})));
 const retry=el('retry-model').click(); checks[1].reject(Error('offline')); await retry;
 checks[0].resolve({ready:true,configured_model:'stale',installed_models:[]}); await tick();
 assert.match(el('model-status').textContent,/offline/); assert.equal(el('generate').disabled,true);
});
test('readiness retry never enables generation while pending', async () => {
 let finish;const el=setup(()=>new Promise(r=>{finish=r;}));await tick();
 await tick();el('context').value='Test';const run=el('generate').click();
 await el('retry-model').click();assert.equal(el('generate').disabled,true);
 finish('done');await run;assert.equal(el('generate').disabled,false);
});
test('generation completion preserves a failed readiness gate', async () => {
 let finish, healthy=true;const el=setup(()=>new Promise(r=>{finish=r;}),async()=>{
 if(!healthy)throw Error('offline');return {ready:true,configured_model:'test',installed_models:[]};
 });await tick();el('context').value='Test';const run=el('generate').click();
 healthy=false;await el('retry-model').click();finish('done');await run;
 assert.equal(el('generate').disabled,true);
});
test('cancellation rejection is visible and never claims generation stopped', async () => {
 let finish;const el=setup(name=>name==='cancel_materialize'?Promise.reject(Error('IPC lost')):new Promise(r=>{finish=r;}));
 await tick();el('context').value='Test';const run=el('generate').click();await el('cancel').click();await tick();
 assert.match(el('status').textContent,/could not be confirmed/i);
 assert.doesNotMatch(el('status').textContent,/was stopped/);
 finish('late');await run;assert.equal(el('result').value,'');
});

test('failed cancellation acknowledgement cannot race a new generation', async () => {
 let finish, acknowledge, calls=0;
 const el=setup(name=>name==='cancel_materialize'?new Promise(r=>{acknowledge=r;}):new Promise(r=>{calls++;finish=r;}));
 await tick();el('context').value='Test';const run=el('generate').click();
 const cancel=el('cancel').click();finish('late');await run;
 assert.equal(el('generate').disabled,true);await el('generate').click();assert.equal(calls,1);
 acknowledge(false);await cancel;assert.equal(el('generate').disabled,false);
 assert.match(el('status').textContent,/No active request acknowledged/);
 assert.equal(el('result').value,'');
});
test('malformed readiness never unlocks generation', async () => {
 let calls=0;const el=setup(async()=>{calls++;},async()=>({ready:'yes',installed_models:[]}));
 await tick();el('context').value='Test';await el('generate').click();
 assert.equal(el('generate').disabled,true);assert.equal(calls,0);
});
