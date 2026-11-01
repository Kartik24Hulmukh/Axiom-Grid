'use strict';

// Pure helper tests. No VS Code host, HTTP, inference, or editor mutation.
const test = require('node:test');
const assert = require('node:assert/strict');
const { planComment, renderComment } = require('../comment.js');
const SOURCE = 'PRIVATE_PROMPT_SOURCE_8721';
const messages = new Map();

function rejectsStatic(action) {
  assert.throws(action, error => {
    assert.ok(error instanceof Error);
    assert.match(error.code, /^COMMENT_[A-Z_]+$/);
    assert.equal(typeof error.message, 'string');
    assert.ok(error.message.length > 0 && error.message.length < 240);
    if (messages.has(error.code)) assert.equal(error.message, messages.get(error.code));
    else messages.set(error.code, error.message);
    assert.ok(!error.message.includes(SOURCE));
    assert.equal(error.cause, undefined);
    return true;
  });
}
const plan = (line, language = 'javascript') => planComment(line, line.length, language);

test('comment plan supports exactly the four JavaScript/TypeScript language IDs', () => {
  for (const language of ['javascript', 'typescript', 'javascriptreact', 'typescriptreact']) {
    assert.deepEqual(plan('// create a useful function', language), {
      instruction: 'create a useful function', indentation: ''
    });
    assert.deepEqual(plan(' \t  //   create a function 😀  ', language), {
      instruction: 'create a function 😀', indentation: ' \t  '
    });
  }
  for (const language of ['python', 'plaintext', 'json', 'JavaScript', 'js', '', null, undefined]) {
    rejectsStatic(() => planComment(`// ${SOURCE}`, SOURCE.length + 3, language));
  }
});

test('nonleading comments, URL slashes, and text literals are not prompt markers', () => {
  for (const line of ['', '  ', 'const x = 1;', 'x(); // add a function',
    'https://example.invalid/path', 'const url = "https://example.invalid";',
    '"// create a function"', "'// create a function'", '`// create a function`',
    'const literal = "// create a function"', '/* comment */', '# comment',
    'x'.repeat(2048) + ' // ordinary long continuation', ' '.repeat(2048) + 'x // ordinary continuation']) {
    assert.equal(plan(line), null, JSON.stringify(line));
  }
});

test('leading marker requires a separator and nonblank instruction', () => {
  for (const line of ['//', '// ', '//\t  ', '//\u00a0', `//${SOURCE}`, `/// ${SOURCE}`, `//! ${SOURCE}`, `//? ${SOURCE}`]) {
    rejectsStatic(() => plan(line));
  }
});

test('leading prompt requires an exact end-of-line UTF-16 cursor', () => {
  const line = `  // ${SOURCE} 😀`;
  assert.deepEqual(planComment(line, line.length, 'typescript'), {
    instruction: `${SOURCE} 😀`, indentation: '  '
  });
  for (const cursor of [0, line.length - 1, line.length + 1, -1, 0.5, NaN,
    Infinity, String(line.length), null, undefined]) {
    rejectsStatic(() => planComment(line, cursor, 'typescript'));
  }
});

test('prompt limit is 1024 UTF-16 code units including indentation and marker', () => {
  const ascii = '// ' + 'x'.repeat(1021);
  assert.equal(ascii.length, 1024);
  assert.equal(plan(ascii).instruction, 'x'.repeat(1021));
  const astral = '// ' + '😀'.repeat(510) + 'x';
  assert.equal(astral.length, 1024);
  assert.equal(plan(astral).instruction, '😀'.repeat(510) + 'x');
  for (const line of [ascii + 'x', '// ' + '😀'.repeat(511), ' '.repeat(1022) + '// x']) {
    rejectsStatic(() => plan(line));
  }
});

test('prompt rejects line breaks, unsafe controls, lone surrogates, and bidi markers', () => {
  const unsafe = ['\ud800', '\udfff', '\r', '\n', '\x7f'];
  for (let cp = 0; cp < 32; cp++) if (cp !== 9) unsafe.push(String.fromCodePoint(cp));
  for (const [lo, hi] of [[0x202a, 0x202e], [0x2066, 0x2069]]) {
    for (let cp = lo; cp <= hi; cp++) unsafe.push(String.fromCodePoint(cp));
  }
  for (const character of unsafe) rejectsStatic(() => plan(`// ${SOURCE}${character}x`));
});

test('render adds exactly one chosen line ending and indentation before untouched raw text', () => {
  const text = '  const x = "😀";\r\n\treturn x;\n\n  ';
  assert.equal(renderComment(text, '\t  '), '\n\t  ' + text);
  assert.equal(renderComment(text, '  ', '\r\n'), '\r\n  ' + text);
  assert.equal(renderComment('x', ''), '\nx');
  assert.equal(renderComment('x\n', '', '\n'), '\nx\n');
});

test('rendered candidate limit includes EOL and indent and uses Unicode scalars', () => {
  for (const text of ['x'.repeat(4095), '😀'.repeat(4095), 'é'.repeat(4095)]) {
    assert.equal(renderComment(text, ''), '\n' + text);
  }
  for (const text of ['x'.repeat(4096), '😀'.repeat(4096), 'é'.repeat(4096), 'x'.repeat(4097)]) {
    rejectsStatic(() => renderComment(text, ''));
  }
  assert.equal(renderComment('😀'.repeat(4093), '\t', '\r\n'), '\r\n\t' + '😀'.repeat(4093));
  rejectsStatic(() => renderComment('😀'.repeat(4094), '\t', '\r\n'));
  assert.equal(renderComment('x', ' '.repeat(1024)), '\n' + ' '.repeat(1024) + 'x');
});

test('render rejects blank text and malformed scalar input', () => {
  for (const text of ['', ' ', '\t\r\n', '\u00a0\u2003', null, undefined, false, 7, {}, [],
    `x\ud800${SOURCE}`, `x\udfff${SOURCE}`]) {
    rejectsStatic(() => renderComment(text, ''));
  }
});

test('render rejects unsafe controls and bidi while preserving tab/LF/CR', () => {
  const unsafe = ['\x7f'];
  for (let cp = 0; cp < 32; cp++) if (![9, 10, 13].includes(cp)) unsafe.push(String.fromCodePoint(cp));
  for (const [lo, hi] of [[0x202a, 0x202e], [0x2066, 0x2069]]) {
    for (let cp = lo; cp <= hi; cp++) unsafe.push(String.fromCodePoint(cp));
  }
  for (const character of unsafe) rejectsStatic(() => renderComment(`${SOURCE}${character}x`, ''));
  assert.equal(renderComment('x\t\n\ry', '\t'), '\n\tx\t\n\ry');
});

test('render rejects nonindentation characters and non-LF/CRLF line-ending options', () => {
  for (const indentation of ['x', '\n', '\r', '\u00a0', '\x00', '\u202e', ' '.repeat(1025), null, 2, {}, []]) {
    rejectsStatic(() => renderComment(SOURCE, indentation));
  }
  for (const eol of ['', '\r', '\n\n', '\r\n\r\n', 'x', '\u2028', null, 7, {}, []]) {
    rejectsStatic(() => renderComment(SOURCE, '', eol));
  }
});
