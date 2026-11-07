'use strict';
// Explicitly dangerous: executes the entire selected file with current-user
// privileges. This is NOT a sandbox. Review and isolate before invoking.
const path = require('node:path');
const tasks = require('./tasks.json').tasks;
const [ack, task, file] = process.argv.slice(2);
if (process.argv.length !== 5 || ack !== '--i-reviewed-this-code' || !Object.hasOwn(tasks, task) || !file) {
  console.error('Usage: node manual-score.cjs --i-reviewed-this-code TASK REVIEWED_FILE');
  console.error('WARNING: executes code with your privileges; use a disposable isolated environment.');
  process.exit(2);
}
let fn;
try { fn = require(path.resolve(file)); if (typeof fn !== 'function') throw Error('not a function'); }
catch (_) { console.log(JSON.stringify({ loaded:false, passed:null, total:tasks[task].cases.length })); process.exit(1); }
let passed = 0;
const cases = tasks[task].cases.map(([input, expected], index) => {
  let value, threw = false;
  try { value = fn(input); } catch (_) { threw = true; }
  const ok = !threw && Object.is(value, expected);
  if (ok) passed++;
  return { case:index+1, ok };
});
console.log(JSON.stringify({ loaded:true, passed, total:cases.length, cases }, null, 2));
process.exitCode = passed === cases.length ? 0 : 1;
