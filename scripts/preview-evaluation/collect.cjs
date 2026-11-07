'use strict';
// Development-only collector. Never loads or executes generated JavaScript.
const fs = require('node:fs');
const path = require('node:path');
const tasks = require('./tasks.json').tasks;
const realClient = require('../../extensions/vscode-lite/client');
const { PreviewSession, makePrompt, stripFence } = require('../../extensions/vscode-lite/state');
const { planComment, renderComment } = require('../../extensions/vscode-lite/comment');

async function collect(task, tokenFile, outputFile, client = realClient) {
  if (!Object.hasOwn(tasks, task)) throw Error('INVALID_TASK');
  // Only read a small regular file. The file path must be trusted; this is not
  // a credential-store or same-user adversary defense.
  const fd = fs.openSync(tokenFile, 'r');
  let token;
  try {
    const stat = fs.fstatSync(fd);
    if (!stat.isFile() || stat.size > 128) throw Error('INVALID_TOKEN_FILE');
    token = fs.readFileSync(fd, 'utf8').trim();
  } finally { fs.closeSync(fd); }
  if (!client.validateToken(token)) throw Error('INVALID_TOKEN_FILE');
  // Reserve the output before any request: never overwrite an existing file.
  const output = fs.openSync(outputFile, 'wx', 0o600);
  try {
    const instruction = tasks[task].instruction;
    const line = '// ' + instruction;
    const comment = planComment(line, line.length, 'javascript');
    const prefix = "'use strict';\n\n";
    const prompt = makePrompt(prefix, '', 'javascript', instruction, line);
    const session = new PreviewSession(client);
    const snapshot = { uri: 'eval-file', version: 1, line: 2, character: line.length };
    const result = await session.run(snapshot, async () => token, prompt, () => true,
      text => renderComment(stripFence(text), comment.indentation, '\n'));
    if (result === null) throw Error('NO_PREVIEW');
    fs.writeFileSync(output, prefix + line + result, 'utf8');
  } finally {
    // Leave a reserved file on failure instead of unlinking a path that may
    // have been replaced since open. It must not be treated as a preview.
    fs.closeSync(output);
  }
}

if (require.main === module) {
  const [task, tokenFile, outputFile] = process.argv.slice(2);
  if (process.argv.length !== 5 || !task || !tokenFile || !outputFile) {
    console.error('Usage: node collect.cjs TASK TOKEN_FILE NEW_OUTPUT_FILE');
    process.exitCode = 2;
  } else {
    collect(task, tokenFile, path.resolve(outputFile)).then(
      () => console.log('Preview saved without execution; review before any testing.'),
      () => { console.error('Collection failed. Check task, pairing, runtime, and output path.'); process.exitCode = 1; }
    );
  }
}
module.exports = { collect };
