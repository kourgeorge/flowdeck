// Exercise the production news client with controlled HTTP/NDJSON responses.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/services/api.ts'), 'utf8');
const compiled = ts.transpileModule(source.replaceAll('import.meta.env', '({})'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;

function client({ get = async () => ({}), fetch = async () => ({}) } = {}) {
  const exports = {};
  vm.runInNewContext(compiled, {
    exports, fetch, URLSearchParams, TextDecoder,
    require: name => {
      if (name === 'axios') return { default: { create: () => ({ get }) } };
      if (name === './authApi') return { getStoredToken: () => null, getStoredUser: () => null };
      throw new Error(`Unexpected import: ${name}`);
    },
  });
  return exports.tickerApi;
}

function streamResponse(parts) {
  let index = 0;
  return { ok: true, body: { getReader: () => ({
    read: async () => index < parts.length
      ? { done: false, value: new TextEncoder().encode(parts[index++]) }
      : { done: true },
    releaseLock() {},
  }) } };
}

async function run() {
  let calls = 0;
  const api = client({ get: async () => ({ data: ++calls === 1
    ? { articles: [], count: 0, error: 'Yahoo unavailable' }
    : { articles: [{ uuid: 'one' }], count: 1 } }) });
  await assert.rejects(api.getNews('AAPL'), /Yahoo unavailable/);
  assert.equal((await api.getNews('AAPL')).count, 1);
  await api.getNews('AAPL');
  assert.equal(calls, 2, 'Provider failures must not enter the browser cache');

  const chunks = [];
  let requestedUrl;
  const streaming = client({ fetch: async url => {
    requestedUrl = url;
    return streamResponse(['{"articles":[],"completed":fal',
      'se}\n{"articles":[],"errors":{"MSFT":"Unavailable"},"completed":true}']);
  } });
  await streaming.getNewsBatchStream(['^GSPC', 'MSFT'], chunk => chunks.push(chunk));
  assert.equal(chunks.length, 2);
  assert.equal(chunks[1].errors.MSFT, 'Unavailable');
  assert.equal(new URL(requestedUrl, 'http://localhost').searchParams.get('tickers'), '^GSPC,MSFT');

  const interrupted = client({ fetch: async () => streamResponse(['{"articles":[],"completed":false}\n']) });
  await assert.rejects(interrupted.getNewsBatchStream(['AAPL'], () => {}), /before all tickers finished/);
  const malformed = client({ fetch: async () => streamResponse(['not json\n']) });
  await assert.rejects(malformed.getNewsBatchStream(['AAPL'], () => {}));
  await assert.rejects(streaming.getNewsBatchStream(['AAPL'], () => { throw new Error('callback failed'); }), /callback failed/);

  const failedBatch = client({ get: async () => ({ data: { articles: [], count: 0, errors: { AAPL: 'Unavailable' } } }) });
  await assert.rejects(failedBatch.getNewsBatch(['AAPL']), /temporarily unavailable/);
  const partialBatch = client({ get: async () => ({ data: { articles: [{ uuid: 'one' }], count: 1, errors: { MSFT: 'Unavailable' } } }) });
  assert.equal((await partialBatch.getNewsBatch(['AAPL', 'MSFT'])).count, 1);
  console.log('Passed: news cache retries, partial errors, URL encoding, split NDJSON, final buffer, and interrupted streams');
}

run().catch(error => { console.error(error); process.exitCode = 1; });
