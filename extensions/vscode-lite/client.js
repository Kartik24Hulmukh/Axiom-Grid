'use strict';

const http = require('node:http');
const { TextDecoder } = require('node:util');

const MAX_BODY_BYTES = 256 * 1024;
// The runtime permits 90 seconds upstream. Allow five seconds of local overhead,
// but never extend this deadline when chunks arrive. Loopback connect gets 2s.
const TOTAL_TIMEOUT_MS = 95000;
const CONNECT_TIMEOUT_MS = 2000;
const MESSAGES = Object.freeze({
  INVALID_TOKEN: 'A valid local runtime token is required.',
  INVALID_CONTEXT: 'Context must be nonblank text within the allowed limit.',
  INVALID_SIGNAL: 'A valid abort signal is required.',
  ABORTED: 'The local request was discarded.',
  TIMEOUT: 'The local request timed out.',
  CONNECTION_ERROR: 'The local runtime request failed.',
  HTTP_ERROR: 'The local runtime rejected the request.',
  RESPONSE_TOO_LARGE: 'The local runtime response exceeded the allowed limit.',
  INVALID_RESPONSE: 'The local runtime returned an invalid response.',
  NOT_READY: 'The local runtime is not ready.'
});

class ClientError extends Error {
  constructor(code) {
    const safeCode = Object.prototype.hasOwnProperty.call(MESSAGES, code)
      ? code : 'CONNECTION_ERROR';
    super(MESSAGES[safeCode]);
    this.name = 'ClientError';
    this.code = safeCode;
    // Do not expose local source paths, native errors, response text or causes.
    this.stack = `${this.name}: ${this.message}`;
  }
}

function validateToken(token) {
  return typeof token === 'string' && token.length === 64
    && !/[^0-9a-fA-F]/.test(token);
}

// Count Unicode scalars, rejecting lone UTF-16 surrogates rather than allowing
// JSON.stringify to silently encode invalid scalar input as escaped surrogates.
function scalarLength(text, maximum) {
  if (typeof text !== 'string') return -1;
  let count = 0;
  for (const scalar of text) {
    const cp = scalar.codePointAt(0);
    if ((cp >= 0xd800 && cp <= 0xdfff) || ++count > maximum) return -1;
  }
  return count;
}

function record(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function request(token, path, body, signal) {
  return new Promise((resolve, reject) => {
    if (!validateToken(token)) return reject(new ClientError('INVALID_TOKEN'));
    if (signal !== undefined && !(signal instanceof AbortSignal)) {
      return reject(new ClientError('INVALID_SIGNAL'));
    }
    if (signal && signal.aborted) return reject(new ClientError('ABORTED'));

    let req;
    let response;
    let settled = false;
    let connectTimer;
    let totalTimer;
    const cleanup = () => {
      clearTimeout(connectTimer);
      clearTimeout(totalTimer);
      if (signal) signal.removeEventListener('abort', abort);
    };
    const fail = code => {
      if (settled) return;
      settled = true;
      cleanup();
      // Disconnect only: runtime cancellation is shared, not request-scoped.
      // This makes no claim that already running backend inference has stopped.
      if (response) response.destroy();
      if (req) req.destroy();
      reject(new ClientError(code));
    };
    const abort = () => fail('ABORTED');

    totalTimer = setTimeout(() => fail('TIMEOUT'), TOTAL_TIMEOUT_MS);
    connectTimer = setTimeout(() => fail('TIMEOUT'), CONNECT_TIMEOUT_MS);
    if (signal) signal.addEventListener('abort', abort, { once: true });

    try {
      const headers = { Authorization: `Bearer ${token}`, Accept: 'application/json' };
      if (body !== undefined) {
        headers['Content-Type'] = 'application/json';
        headers['Content-Length'] = Buffer.byteLength(body);
      }
      // Numeric IPv4 only; no URL input, DNS, environment proxy, redirect
      // following, Origin, Sec-Fetch headers, or pooled/reused sockets.
      req = http.request({
        protocol: 'http:',
        hostname: '127.0.0.1',
        port: 7437,
        family: 4,
        path,
        method: body === undefined ? 'GET' : 'POST',
        headers,
        agent: false,
        maxHeaderSize: 16384
      }, res => {
        response = res;
        res.on('error', () => fail('CONNECTION_ERROR'));
        if (settled) { res.destroy(); return; }
        // Reject redirects and every other non-2xx before adding a data handler.
        if (!(res.statusCode >= 200 && res.statusCode < 300)) {
          fail('HTTP_ERROR');
          return;
        }
        const length = res.headers['content-length'];
        let declared;
        if (length !== undefined) {
          if (typeof length !== 'string' || !/^[0-9]+$/.test(length)) {
            fail('INVALID_RESPONSE');
            return;
          }
          declared = Number(length);
          if (!Number.isSafeInteger(declared) || declared > MAX_BODY_BYTES) {
            fail('RESPONSE_TOO_LARGE');
            return;
          }
        }
        let bytes = 0;
        const chunks = [];
        res.on('aborted', () => fail('CONNECTION_ERROR'));
        res.on('close', () => {
          if (!res.complete) fail('CONNECTION_ERROR');
        });
        res.on('data', chunk => {
          if (settled) return;
          bytes += chunk.length;
          if (bytes > MAX_BODY_BYTES) { fail('RESPONSE_TOO_LARGE'); return; }
          chunks.push(chunk);
        });
        res.on('end', () => {
          if (settled) return;
          if (!res.complete || (declared !== undefined && bytes !== declared)) {
            fail('INVALID_RESPONSE');
            return;
          }
          let value;
          try {
            // Preserve a BOM so JSON.parse rejects it, rather than stripping it.
            const text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true })
              .decode(Buffer.concat(chunks, bytes));
            value = JSON.parse(text);
          } catch (_) {
            fail('INVALID_RESPONSE');
            return;
          }
          settled = true;
          cleanup();
          resolve(value);
        });
      });
      req.on('error', () => fail('CONNECTION_ERROR'));
      req.on('socket', socket => {
        if (settled) { socket.destroy(); return; }
        if (!socket.connecting) clearTimeout(connectTimer);
        else socket.once('connect', () => clearTimeout(connectTimer));
      });
      if (body === undefined) req.end();
      else req.end(body);
    } catch (_) {
      fail('CONNECTION_ERROR');
    }
  });
}

async function readiness(token, { signal } = {}) {
  const value = await request(token, '/readiness', undefined, signal);
  if (!record(value)
      || typeof value.configured_model !== 'string'
      || value.configured_model.length < 1 || value.configured_model.length > 256
      || /[^\x21-\x7e]/.test(value.configured_model)
      || typeof value.expected_digest !== 'string'
      || value.expected_digest.length !== 64 || /[^0-9a-f]/.test(value.expected_digest)
      || value.identity_check_scope !== 'reported-only'
      || !Array.isArray(value.installed_models)
      || typeof value.ready !== 'boolean') {
    throw new ClientError('INVALID_RESPONSE');
  }
  let matchingModel;
  let matchingCount = 0;
  for (const model of value.installed_models) {
    if (!record(model)
        || typeof model.name !== 'string'
        || model.name.length < 1 || model.name.length > 256
        || /[^\x21-\x7e]/.test(model.name)
        || !Number.isSafeInteger(model.size) || model.size < 0
        || typeof model.digest !== 'string' || model.digest.length > 256) {
      throw new ClientError('INVALID_RESPONSE');
    }
    if (model.name === value.configured_model) {
      matchingModel = model;
      matchingCount += 1;
    }
  }
  // Consistency of reported inventory only, not attestation. The runtime's
  // fresh generation preflight remains authoritative for every request.
  if (matchingCount !== 1 || matchingModel.size <= 0
      || matchingModel.digest !== value.expected_digest) {
    throw new ClientError('INVALID_RESPONSE');
  }
  if (value.ready !== true) throw new ClientError('NOT_READY');
  return {
    ready: true,
    configured_model: value.configured_model,
    expected_digest: value.expected_digest,
    identity_check_scope: 'reported-only',
    installed_model_count: value.installed_models.length
  };
}

async function generate(token, context, { signal } = {}) {
  if (!validateToken(token)) throw new ClientError('INVALID_TOKEN');
  if (scalarLength(context, 16000) < 1 || context.trim().length === 0) {
    throw new ClientError('INVALID_CONTEXT');
  }
  const value = await request(token, '/materialize', JSON.stringify({ context, mode: 'code' }), signal);
  if (!record(value) || scalarLength(value.suggestion, 4096) < 1
      || value.suggestion.trim().length === 0
      || /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069]/
        .test(value.suggestion)) {
    throw new ClientError('INVALID_RESPONSE');
  }
  return value.suggestion;
}

module.exports = { readiness, generate, validateToken, ClientError };
