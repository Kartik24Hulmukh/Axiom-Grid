const test = require('node:test');
const assert = require('node:assert/strict');
const {PreviewSession, sameSnapshot, makePrompt} = require('../state');
const tick = () => new Promise(r => setImmediate(r));
const snap = {uri:'file:///public-fixture.js',version:1,line:0,character:2};
function deferred() {let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
test('complete prompt includes bounded prefix/suffix; rejects empty/oversized complete prompt',()=>{
 assert.match(makePrompt('function x(){','}','javascript'), /<PREFIX>\nfunction x\(\)\{/);
 assert.match(makePrompt('x','y','unsafe\nlabel'), /short text code/);
 assert.throws(()=>makePrompt(' ','\n','x'), /EMPTY_CONTEXT/);
 assert.throws(()=>makePrompt('a'.repeat(16000),'','x'), /CONTEXT_TOO_LARGE/);
 assert.doesNotThrow(()=>makePrompt('😀'.repeat(7000),'','x'));
});
test('snapshot binds URI, version, line and cursor',()=>{
 assert.equal(sameSnapshot(snap,{...snap}),true);
 for(const key of ['uri','version','line','character']) assert.equal(sameSnapshot(snap,{...snap,[key]:'other'}),false);
 assert.equal(sameSnapshot(null,snap),false);
});
test('reservation precedes SecretStorage await; concurrent request never loads token',async()=>{
 const secret=deferred();let calls=0;const s=new PreviewSession({readiness:async()=>{calls++;},generate:async()=> 'literal'});
 const first=s.run(snap,()=>secret.promise,'prompt',()=>true);
 assert.equal(s.pending,true);
 await assert.rejects(s.run(snap,()=>{throw Error('must not load');},'p',()=>true), /BUSY/);
 secret.resolve('token');assert.equal(await first,'literal');assert.equal(calls,1);assert.equal(s.peek(snap),'literal');
});
for(const stage of ['secret','readiness','generation'])test(`invalidation during ${stage} drops late output and retains admission until settlement`,async()=>{
 const d=deferred();let checks=0,runs=0;
 const s=new PreviewSession({readiness:async()=>{checks++;if(stage==='readiness')await d.promise;},generate:async()=>{runs++;return stage==='generation'?d.promise:'new';}});
 const work=s.run(snap,()=>stage==='secret'?d.promise:Promise.resolve('token'),'p',()=>true);
 await tick();s.invalidate();assert.equal(s.pending,true);assert.equal(s.peek(snap),null);
 await assert.rejects(s.run(snap,async()=> 't','p',()=>true),/BUSY/);
 d.resolve(stage==='secret'?'token':'late');assert.equal(await work,null);assert.equal(s.pending,false);assert.equal(s.peek(snap),null);
 if(stage==='secret')assert.equal(checks,0);
 if(stage==='readiness')assert.equal(runs,0);
});
test('current snapshot predicate rechecked before any context request and after output',async()=>{
 let current=true;const ready=deferred();let sent=0;
 const s=new PreviewSession({readiness:()=>ready.promise,generate:async()=>{sent++;return 'x';}});
 const p=s.run(snap,async()=> 't','p',()=>current);await tick();current=false;ready.resolve();assert.equal(await p,null);assert.equal(sent,0);
});
test('failure clears reservation; stale failure is suppressed and a fresh request works',async()=>{
 const d=deferred();let n=0;const s=new PreviewSession({readiness:async()=>{},generate:async()=>++n===1?d.promise:'fresh'});
 const p=s.run(snap,async()=> 't','p',()=>true);await tick();s.invalidate();d.reject(Error('private underlying error'));
 assert.equal(await p,null);assert.equal(s.pending,false);
 assert.equal(await s.run({...snap,version:2},async()=> 't','p',()=>true),'fresh');assert.equal(s.peek(snap),null);
});
test('current request failure propagates but pending is always released',async()=>{
 const s=new PreviewSession({readiness:async()=>{throw Error('fixture');}});
 await assert.rejects(s.run(snap,async()=> 't','p',()=>true),/fixture/);assert.equal(s.pending,false);assert.equal(s.candidate,null);
});
test('comment instruction supports empty source and bounds full wrapped prompt',()=>{
 const prompt=makePrompt('','','typescript','write a helper');
 assert.match(prompt,/<USER_INSTRUCTION>\nwrite a helper\n<\/USER_INSTRUCTION>/);
 assert.throws(()=>makePrompt('','','javascript',' '),/INVALID_INSTRUCTION/);
 assert.throws(()=>makePrompt('x'.repeat(15800),'','javascript','write code'),/CONTEXT_TOO_LARGE/);
});
test('candidate transform publishes only a bounded literal string and releases reservation on failure',async()=>{
 const s=new PreviewSession({readiness:async()=>{},generate:async()=> 'code'});
 for(const invalid of [()=>null,()=>Promise.resolve('text'),()=> 'x'.repeat(4097),()=> ' ']){
  await assert.rejects(s.run(snap,async()=> 't','p',()=>true,invalid),/INVALID_CANDIDATE/);
  assert.equal(s.candidate,null);assert.equal(s.pending,false);
 }
 assert.equal(await s.run(snap,async()=> 't','p',()=>true,t=>'\n'+t),'\ncode');
});
test('stale generation never reaches candidate transform',async()=>{
 const d=deferred();let current=true,transforms=0;
 const s=new PreviewSession({readiness:async()=>{},generate:()=>d.promise});
 const p=s.run(snap,async()=> 't','p',()=>current,()=>{transforms++;return 'bad';});
 await tick();current=false;d.resolve('late');assert.equal(await p,null);assert.equal(transforms,0);assert.equal(s.candidate,null);
});
