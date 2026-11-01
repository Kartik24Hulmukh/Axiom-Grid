'use strict';

// Static manifest checks only: no extension activation or VS Code host needed.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));
const COMMANDS = Object.freeze([
  'axiomLite.complete',
  'axiomLite.setToken',
  'axiomLite.clearToken',
  'axiomLite.discard'
]);

const sorted = values => [...values].sort();

test('manifest release version is exactly 0.1.1', () => {
  assert.equal(manifest.version, '0.1.1');
});

test('manifest contributes exactly the established four commands', () => {
  assert.ok(Array.isArray(manifest.contributes?.commands));
  assert.deepEqual(sorted(manifest.contributes.commands.map(entry => entry.command)), sorted(COMMANDS));
});

test('activation is limited to the same four explicit commands', () => {
  assert.ok(Array.isArray(manifest.activationEvents));
  assert.deepEqual(sorted(manifest.activationEvents), sorted(COMMANDS.map(command => `onCommand:${command}`)));
});

test('Ctrl+Alt+K explicitly invokes completion on both default and Mac platforms', () => {
  const bindings = manifest.contributes?.keybindings;
  assert.ok(Array.isArray(bindings));
  const complete = bindings.filter(binding => binding.command === 'axiomLite.complete');
  assert.equal(complete.length, 1, 'completion has one unambiguous shortcut definition');
  assert.equal(complete[0].key, 'ctrl+alt+k');
  assert.equal(complete[0].mac, 'ctrl+alt+k');
  for (const binding of bindings) {
    if (binding === complete[0]) continue;
    assert.notEqual(binding.key, 'ctrl+alt+k', 'default shortcut must not conflict with another command');
    assert.notEqual(binding.mac, 'ctrl+alt+k', 'Mac shortcut must not conflict with another command');
  }
});

test('completion shortcut requires every trusted single-cursor writable-file guard', () => {
  const complete = manifest.contributes?.keybindings?.find(binding => binding.command === 'axiomLite.complete');
  assert.ok(complete, 'completion shortcut is present');
  assert.equal(typeof complete.when, 'string');
  // Exact conjunctions prohibit OR branches or omitted/negated safety guards.
  // Quotes around the literal file scheme and ordinary spacing are equivalent.
  const clauses = complete.when.split('&&').map(clause => clause.trim()
    .replace(/resourceScheme\s*==\s*(['"])file\1/g, 'resourceScheme == file')
    .replace(/resourceScheme\s*==\s*file/g, 'resourceScheme == file'));
  assert.deepEqual(sorted(clauses), sorted([
    'editorTextFocus',
    'resourceScheme == file',
    'isWorkspaceTrusted',
    '!editorHasSelection',
    '!editorHasMultipleSelections',
    '!editorReadonly'
  ]));
});

test('manifest has no runtime package or extension dependencies', () => {
  for (const field of ['dependencies', 'optionalDependencies', 'extensionDependencies',
    'bundledDependencies', 'bundleDependencies']) {
    if (manifest[field] === undefined) continue;
    const value = manifest[field];
    assert.ok(value !== null && typeof value === 'object', `${field} must be absent or empty`);
    assert.equal(Object.keys(value).length, 0, `${field} must not add runtime dependencies`);
  }
});
