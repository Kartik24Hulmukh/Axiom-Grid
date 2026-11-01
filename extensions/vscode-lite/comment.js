'use strict';
const LANGUAGES = new Set(['javascript', 'typescript', 'javascriptreact', 'typescriptreact']);
function fail(code) { const error = new Error(code); error.code = code; throw error; }
function safeUnicode(value, multiline) {
  if ((multiline ? /[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\u202A-\u202E\u2066-\u2069]/ : /[\x00-\x08\x0A-\x1F\x7F\u202A-\u202E\u2066-\u2069]/).test(value)) return false;
  for (const scalar of value) {
    const n = scalar.codePointAt(0);
    if (n >= 0xD800 && n <= 0xDFFF) return false;
  }
  return true;
}
// Textual, explicit marker recognition, not JavaScript lexical analysis.
// The caller supplies at most the first 1,025 UTF-16 units of the current line.
function planComment(line, cursor, language) {
  if (typeof line !== 'string') fail('COMMENT_INVALID');
  if (!/^[ \t]*\/\//.test(line)) return null;
  if (line.length > 1024) fail('COMMENT_TOO_LARGE');
  if (!safeUnicode(line, false)) fail('COMMENT_INVALID');
  if (!Number.isInteger(cursor) || cursor !== line.length) fail('COMMENT_CURSOR');
  if (!LANGUAGES.has(language)) fail('COMMENT_LANGUAGE');
  const match = /^([ \t]*)\/\/[ \t]+(.*)$/.exec(line);
  if (!match || !match[2].trim()) fail('COMMENT_INVALID');
  return {instruction: match[2].trim(), indentation: match[1]};
}
function renderComment(text, indentation, eol = '\n') {
  if (typeof text !== 'string' || !text.trim() || !safeUnicode(text, true)
      || typeof indentation !== 'string' || !/^[ \t]{0,1024}$/.test(indentation)
      || (eol !== '\n' && eol !== '\r\n')) fail('COMMENT_OUTPUT_INVALID');
  const result = eol + indentation + text;
  if ([...result].length > 4096) fail('COMMENT_OUTPUT_INVALID');
  return result;
}
module.exports = {planComment, renderComment};