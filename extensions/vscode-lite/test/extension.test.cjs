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
 const document={uri:{scheme:'file',toString:()=> 'file:///fixture.js'},languageId:'javascript',lineCount:1,isClosed:false,
 get version(){return version;},lineAt(){return {range:{end:new Position(0,text.length)}};},offsetAt(p){return p.character;},positionAt(n){return new Position(0,n);},
 getText(range){assert.ok(range,'No whole-document read');reads.push(range);return text.slice(range.start.character,range.end.character);}};
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
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../extension.js'),'utf8'),{module,require(name){if(name==='vscode')return vscode;if(name==='./client')return client;if(name==='./state')return require('../state');throw Error('Unexpected dependency');},Promise});
 module.exports.activate(context);
 return {vscode,editor,document,context,client,calls,reads,messages,executed,inputs,status,secretChanges,
 command:name=>commands.get('axiomLite.'+name)(),
 preview:()=>provider.provideInlineCompletionItems(document,editor.selection.active),
 setGet:fn=>{get=fn;},setStore:fn=>{store=fn;},setDelete:fn=>{del=fn;},
 edit(value){text=value;version++;editor.selection.active=new Position(0,text.length);textChanges.fire({document});},
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
 const a=fixture();await a.command('complete');assert.equal(a.reads.length,2);
 a.inputs.push('b'.repeat(64));let saved;a.setStore(async(k,v)=>{saved={k,v};});await a.command('setToken');assert.equal(saved.k,'axiomLite.runtimeToken');assert.equal(saved.v,'b'.repeat(64));
 assert.ok(a.messages.every(s=>!s.includes(saved.v)));assert.equal(a.vscode.workspace.getConfiguration,undefined);
});
