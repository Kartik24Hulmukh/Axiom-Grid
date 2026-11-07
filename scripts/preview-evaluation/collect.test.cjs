'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const cp = require('node:child_process');
const { collect } = require('./collect.cjs');
const realClient = require('../../extensions/vscode-lite/client');
const tasks = require('./tasks.json').tasks;
function temporary(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'axiom-eval-'));
  t.after(() => fs.rmSync(dir, {recursive:true, force:true}));
  const token = path.join(dir, 'token'); fs.writeFileSync(token, 'a'.repeat(64), {mode:0o600});
  return {dir, token, output:path.join(dir, 'out.js')};
}
test('collection makes one explicit request without executing output or sending cases', async t => {
  const x=temporary(t); let calls=0; const marker=path.join(x.dir,'SHOULD_NOT_RUN');
  const client={validateToken:realClient.validateToken, async readiness(){}, async generate(_token,prompt){
    calls++; assert.ok(prompt.includes(tasks.bytes.instruction)); assert.ok(!prompt.includes('1023 B'));
    return `require('node:fs').writeFileSync(${JSON.stringify(marker)}, 'x');`;
  }};
  await collect('bytes',x.token,x.output,client);
  assert.equal(calls,1); assert.match(fs.readFileSync(x.output,'utf8'),/SHOULD_NOT_RUN/);
  assert.equal(fs.existsSync(marker),false);
  if (process.platform !== 'win32') assert.equal(fs.statSync(x.output).mode & 0o777, 0o600);
});
test('invalid task, token, and existing output fail before requests', async t => {
  const x=temporary(t);let calls=0;const client={validateToken:realClient.validateToken,async readiness(){calls++},async generate(){calls++;return 'ok'}};
  await assert.rejects(collect('missing',x.token,x.output,client));
  fs.writeFileSync(x.token,'bad');await assert.rejects(collect('bytes',x.token,x.output,client));
  fs.writeFileSync(x.token,'a'.repeat(64));fs.writeFileSync(x.output,'do not overwrite');
  await assert.rejects(collect('bytes',x.token,x.output,client));
  assert.equal(calls,0);assert.equal(fs.readFileSync(x.output,'utf8'),'do not overwrite');
});
test('failed generation leaves an empty reserved output, never a preview', async t => {
  const x=temporary(t);const client={validateToken:realClient.validateToken,async readiness(){},async generate(){throw Error('private source')}};
  await assert.rejects(collect('bytes',x.token,x.output,client));assert.equal(fs.readFileSync(x.output,'utf8'),'');
});
test('blank or oversized candidate is discarded', async t => {
  const x=temporary(t);for(const [i,value] of [' ', 'x'.repeat(4097)].entries()) {
    const output=x.output+i;const client={validateToken:realClient.validateToken,async readiness(){},async generate(){return value}};
    await assert.rejects(collect('bytes',x.token,output,client));assert.equal(fs.readFileSync(output,'utf8'),'');
  }
});
test('collector CLI reports static errors without token contents', t => {
  const x=temporary(t);fs.writeFileSync(x.token,'SECRET_PRIVATE_INVALID');
  const run=cp.spawnSync(process.execPath,[path.join(__dirname,'collect.cjs'),'bytes',x.token,x.output],{encoding:'utf8'});
  assert.equal(run.status,1);assert.ok(!`${run.stdout}${run.stderr}`.includes('SECRET_PRIVATE_INVALID'));assert.equal(fs.existsSync(x.output),false);
});
test('scorer requires explicit review acknowledgement before loading', t => {
  const x=temporary(t), marker=path.join(x.dir,'executed');
  fs.writeFileSync(x.output,`require('node:fs').writeFileSync(${JSON.stringify(marker)}, 'x'); module.exports=()=>null;`);
  const run=cp.spawnSync(process.execPath,[path.join(__dirname,'manual-score.cjs'),'bytes',x.output]);
  assert.equal(run.status,2);assert.equal(fs.existsSync(marker),false);
});
test('scorer counts fixed cases for a reviewed test fixture', t => {
  const x=temporary(t);fs.writeFileSync(x.output,"module.exports = bytes => Number.isSafeInteger(bytes) && bytes >= 0 ? (bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KiB`) : null;");
  const run=cp.spawnSync(process.execPath,[path.join(__dirname,'manual-score.cjs'),'--i-reviewed-this-code','bytes',x.output],{encoding:'utf8'});
  assert.equal(run.status,0);const result=JSON.parse(run.stdout);assert.equal(result.passed,12);assert.equal(result.total,12);
});
