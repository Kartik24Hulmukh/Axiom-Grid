const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const realClient = require('../client');
const tick = () => new Promise(r => setImmediate(r));
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function emitter(){const listeners=[];return {event(fn){listeners.push(fn);return {dispose(){}};},fire(value){for(const f of listeners)f(value);}};}
class Position{constructor(line,character){this.line=line;this.character=character;}isEqual(p){return this.line===p.line&&this.character===p.character;}}
class Range{constructor(start,end){this.start=start;this.end=end;}}
function fixture(){
 const commands=new Map(),messages=[],executed=[],calls=[],inputs=[],reads=[];
 const textChanges=emitter(),selectionChanges=emitter(),editorChanges=emitter(),secretChanges=emitter(),cancel=emitter();
 let text='function example() {', stored='a'.repeat(64), version=1, get=async()=>stored,store=async(_k,v)=>{stored=v;secretChanges.fire({key:'axiomLite.runtimeToken'});},del=async()=>{stored=undefined;secretChanges.fire({key:'axiomLite.runtimeToken'});};
 const offsetAt=p=>text.split('\n').slice(0,p.line).reduce((n,s)=>n+s.length+1,0)+p.character;
 const positionAt=n=>{const parts=text.slice(0,n).split('\n');return new Position(parts.length-1,parts.at(-1).length);};
 const document={uri:{scheme:'file',toString:()=> 'file:///fixture.js'},languageId:'javascript',isClosed:false,eol:1,
 get lineCount(){return text.split('\n').length;},get version(){return version;},lineAt(line){return {range:{end:new Position(line,text.split('\n')[line].replace(/\r$/,'').length)}};},offsetAt,positionAt,
 getText(range){assert.ok(range,'No whole-document read');reads.push(range);return text.slice(offsetAt(range.start),offsetAt(range.end));}};
 const editor={document,selection:{isEmpty:true,active:new Position(0,text.length)},selections:[{}]};
 let provider;
 const status={text:'',show(){},dispose(){}};
 const context={subscriptions:[],secrets:{get:k=>get(k),store:(k,v)=>store(k,v),delete:k=>del(k),onDidChange:secretChanges.event}};
 const client={...realClient,readiness:async token=>{calls.push(['readiness',token]);if(!realClient.validateToken(token))throw new realClient.ClientError('INVALID_TOKEN');},generate:async(token,prompt)=>{calls.push(['generate',token,prompt]);return 'return 42;';}};
 const vscode={env:{remoteName:undefined,uiKind:1},UIKind:{Desktop:1,Web:2},StatusBarAlignment:{Right:2},ProgressLocation:{Notification:15},Range,
 InlineCompletionItem:class{constructor(insertText,range){this.insertText=insertText;this.range=range;}},
 workspace:{isTrusted:true,onDidChangeTextDocument:textChanges.event},
 languages:{registerInlineCompletionItemProvider(_selector,p){provider=p;return {dispose(){}};}},
 commands:{registerCommand(name,fn){commands.set(name,fn);return {dispose(){}};},async executeCommand(name){executed.push(name);}},
 window:{activeTextEditor:editor,createStatusBarItem(){return status;},onDidChangeTextEditorSelection:selectionChanges.event,onDidChangeActiveTextEditor:editorChanges.event,
 showWarningMessage(s){messages.push(s);},showInformationMessage(s){messages.push(s);},async showInputBox(options){assert.equal(options.password,true);return inputs.shift();},
 withProgress(_options,fn){return fn({}, {isCancellationRequested:false,onCancellationRequested:cancel.event});}}};
 const module={exports:{}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../extension.js'),'utf8'),{module,require(name){if(name==='vscode')return vscode;if(name==='./client')return client;if(name==='./state')return require('../state');if(name==='./comment')return require('../comment');throw Error('Unexpected dependency');},Promise});
 module.exports.activate(context);
 return {vscode,editor,document,context,client,calls,reads,messages,executed,inputs,status,secretChanges,
 command:name=>commands.get('axiomLite.'+name)(),
 preview:()=>provider.provideInlineCompletionItems(document,editor.selection.active),
 setGet:fn=>{get=fn;},setStore:fn=>{store=fn;},setDelete:fn=>{del=fn;},
 edit(value){text=value;version++;editor.selection.active=positionAt(text.length);textChanges.fire({document});},
 contents:()=>text,setCursor(line,character){editor.selection.active=new Position(line,character);selectionChanges.fire({textEditor:editor});},
 move(){editor.selection.active=new Position(0,0);selectionChanges.fire({textEditor:editor});},
 cancel(){cancel.fire();},changeEditor(){vscode.window.activeTextEditor=undefined;editorChanges.fire(undefined);}
 };
}
test('activation and passive provider never perform inference; no automatic edit API exists',()=>{
 const a=fixture();assert.deepEqual(a.calls,[]);assert.equal(a.preview().length,0);assert.deepEqual(a.executed,[]);assert.equal(a.editor.edit,undefined);
});
test('explicit completion yields literal zero-width preview; acceptance/edit invalidates without new HTTP',async()=>{
 const a=fixture();a.client.generate=async(_t,p)=>{a.calls.push(['generate',p]);return '<script>literal</script>';};
 await a.command('complete');assert.equal(a.calls.length,2);const p=a.preview()[0];assert.equal(p.insertText,'<script>literal</script>');assert.equal(p.range.start,p.range.end);
 assert.deepEqual(a.executed,['editor.action.inlineSuggest.trigger']);assert.ok(!a.calls[1][1].includes('file:///fixture'));
 assert.equal(a.preview().length,1);assert.equal(a.calls.length,2);a.edit('accepted text');assert.equal(a.preview().length,0);assert.equal(a.calls.length,2);
});
for(const reason of ['untrusted','remote','web','virtual','selection','multiple','closed'])test(`unsupported ${reason} editor never loads token or contacts runtime`,async()=>{
 const a=fixture();a.setGet(()=>{throw Error('must not access secrets');});
 if(reason==='untrusted')a.vscode.workspace.isTrusted=false;
 if(reason==='remote')a.vscode.env.remoteName='ssh-remote';
 if(reason==='web')a.vscode.env.uiKind=2;
 if(reason==='virtual')a.document.uri.scheme='vscode-remote';
 if(reason==='selection')a.editor.selection.isEmpty=false;
 if(reason==='multiple')a.editor.selections=[{},{}];
 if(reason==='closed')a.document.isClosed=true;
 await a.command('complete');assert.equal(a.calls.length,0);assert.equal(a.preview().length,0);
});
test('SecretStorage get is inside single flight and change event prevents old token from being sent',async()=>{
 const a=fixture(),get=deferred();let gets=0;a.setGet(()=>{gets++;return get.promise;});
 const p=a.command('complete');await tick();await a.command('complete');assert.equal(gets,1);
 a.secretChanges.fire({key:'axiomLite.runtimeToken'});get.resolve('a'.repeat(64));await p;assert.equal(a.calls.length,0);assert.equal(a.preview().length,0);
});
for(const action of ['edit','move','changeEditor','cancel'])test(`${action} during inference suppresses late output and does not issue global cancel`,async()=>{
 const a=fixture(),done=deferred();a.client.generate=async()=>{a.calls.push(['generate']);return done.promise;};
 const p=a.command('complete');await tick();a[action](action==='edit'?'new code':undefined);await a.command('complete');assert.equal(a.calls.length,2);
 done.resolve('stale');await p;assert.equal(a.preview().length,0);assert.ok(!a.executed.includes('editor.action.inlineSuggest.trigger'));
 assert.ok(a.calls.every(c=>c[0]!=='cancel'));
});
for(const operation of ['store','delete'])test(`pending SecretStorage ${operation} blocks complete and serializes mutation commands`,async()=>{
 const a=fixture(),done=deferred();let mutations=0;
 if(operation==='store'){a.inputs.push('b'.repeat(64));a.setStore(async()=>{mutations++;await done.promise;});}
 else a.setDelete(async()=>{mutations++;await done.promise;});
 const p=a.command(operation==='store'?'setToken':'clearToken');await tick();await a.command('complete');assert.equal(a.calls.length,0);
 await a.command('clearToken');assert.equal(mutations,1);
 done.resolve();await p;await a.command('complete');assert.equal(a.calls.length,2);
});
test('missing token errors are static and no raw exception or secret is shown',async()=>{
 const a=fixture();a.setGet(async()=>undefined);await a.command('complete');assert.match(a.messages.at(-1),/Set Runtime Token/);
 a.setGet(async()=>{throw Error('SYNTHETIC_PRIVATE_PATH_AND_TOKEN');});await a.command('complete');assert.ok(a.messages.every(s=>!s.includes('SYNTHETIC_PRIVATE')));
});
test('bounded context reads and token prompt persistence never use normal configuration',async()=>{
 const a=fixture();await a.command('complete');assert.equal(a.reads.length,3);assert.ok(a.reads[0].end.character-a.reads[0].start.character<=1025);
 a.inputs.push('b'.repeat(64));let saved;a.setStore(async(k,v)=>{saved={k,v};});await a.command('setToken');assert.equal(saved.k,'axiomLite.runtimeToken');assert.equal(saved.v,'b'.repeat(64));
 assert.ok(a.messages.every(s=>!s.includes(saved.v)));assert.equal(a.vscode.workspace.getConfiguration,undefined);
});
test('explicit slash instruction is sent as instruction and previews below retained line, without edits',async()=>{
 const a=fixture(),source='// retain this earlier comment\nconst start = 1;\n  // create a sum function';
 a.edit(source);await a.command('complete');
 assert.equal(a.calls.length,2);const prompt=a.calls[1][2];
 assert.ok(prompt.includes('<USER_INSTRUCTION>\ncreate a sum function\n</USER_INSTRUCTION>'));
 assert.ok(prompt.includes('<PREFIX>\n// retain this earlier comment\nconst start = 1;\n\n</PREFIX>'));
 assert.ok(!prompt.includes('  // create a sum function'));
 const item=a.preview()[0];assert.equal(item.insertText,'\n  return 42;');assert.equal(item.range.start,item.range.end);
 assert.equal(a.contents(),source);assert.equal(a.reads[0].end.character-a.reads[0].start.character,source.split('\n').at(-1).length);
 a.edit(source+' ');assert.equal(a.preview().length,0);assert.equal(a.calls.length,2);
});
test('comment rendering preserves raw internal whitespace and uses captured CRLF only for prefix',async()=>{
 const a=fixture();a.document.eol=2;a.edit('const x = 1;\r\n\t// add a helper');
 a.client.generate=async()=>'\tfirst();\n  second();\r\nthird();';
 await a.command('complete');assert.equal(a.preview()[0].insertText,'\r\n\t\tfirst();\n  second();\r\nthird();');
});
for(const marker of ['//','//   ','/// doc','//! urgent','//? query','// no\n//\u0000 invalid','// bad\u202Etext','// bad\uD800','// '+ 'a'.repeat(1022),' '.repeat(1100)+'// prompt'])
 test('malformed or oversized anchored comment never reads credentials or sends context: '+JSON.stringify(marker.slice(0,35)),async()=>{
  const a=fixture();a.edit(marker);a.setGet(()=>{throw Error('must not load credentials');});
  await a.command('complete');assert.equal(a.calls.length,0);assert.equal(a.preview().length,0);
  assert.equal(a.reads.length,1);assert.ok(a.reads[0].end.character-a.reads[0].start.character<=1025);
 });
test('comment instruction requires supported language and end-of-line cursor',async()=>{
 for(const reason of ['language','cursor']){
  const a=fixture();a.edit('// implement sum');if(reason==='language')a.document.languageId='python';else a.setCursor(0,5);
  a.setGet(()=>{throw Error('must not load credentials');});await a.command('complete');assert.equal(a.calls.length,0);
 }
});
for(const unit of [' ','\t'])for(const count of [1023,1024,1025])
 test(`bounded-marker delimiter split: ${count} ${unit===' '?'spaces':'tabs'} never loads credentials`,async()=>{
  const a=fixture();a.edit(unit.repeat(count)+'// prompt');let credentialLoads=0;
  a.setGet(()=>{credentialLoads++;throw Error('must not load credentials');});
  await a.command('complete');assert.equal(credentialLoads,0);assert.equal(a.calls.length,0);
  assert.equal(a.reads.length,1);assert.ok(a.reads[0].end.character-a.reads[0].start.character<=1025);
 });
test('ordinary long-line continuation and inline slash strings retain original path',async()=>{
 for(const source of ['a'.repeat(2500),'const url = "https://example.invalid";','const value = "// write code";']){
  const a=fixture();a.edit(source);await a.command('complete');assert.equal(a.calls.length,2);
  assert.ok(!a.calls[1][2].includes('<USER_INSTRUCTION>'));assert.equal(a.preview()[0].insertText,'return 42;');
 }
});
test('comment output exceeding final candidate budget is rejected, never truncated or published',async()=>{
 const a=fixture();a.edit('  // generate code');a.client.generate=async()=> 'x'.repeat(4094);
 await a.command('complete');assert.equal(a.preview().length,0);assert.ok(a.messages.at(-1).includes('no suggestion was inserted'));
 assert.ok(!a.executed.includes('editor.action.inlineSuggest.trigger'));
});
test('comment inference still suppresses late output after prompt edits',async()=>{
 const a=fixture(),d=deferred();a.edit('// original instruction');a.client.generate=async()=>d.promise;
 const p=a.command('complete');await tick();a.edit('// different instruction');d.resolve('stale');await p;
 assert.equal(a.preview().length,0);assert.ok(!a.executed.includes('editor.action.inlineSuggest.trigger'));
});
