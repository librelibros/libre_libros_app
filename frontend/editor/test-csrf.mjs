import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

function fixture() {
  const dom = new JSDOM('<meta name="csrf-token" content="session-test-token">', {
    url: 'https://books.example/books/1/edit', runScripts: 'outside-only',
  });
  dom.window.Headers = Headers;
  const originalFetch = () => { throw new Error('Tests must not access the network'); };
  dom.window.fetch = originalFetch;
  dom.window.eval(readFileSync(new URL('../../app/static/js/csrf.js', import.meta.url), 'utf8'));
  return { dom, options: dom.window.LibreLibrosCSRF.options, originalFetch };
}

test('POST preview/save preserve body, headers and abort while attaching session token', () => {
  const { dom, options, originalFetch } = fixture();
  try {
    const body = new dom.window.FormData();
    body.append('content', '# Borrador');
    body.append('assets', new dom.window.File(['bytes'], 'imagen.png'));
    const signal = new AbortController().signal;
    for (const path of ['/books/preview', 'https://books.example/books/1/edit']) {
      const init = options(path, { method: 'POST', body, signal, headers: { Accept: 'text/html' } });
      assert.equal(init.headers.get('X-CSRF-Token'), 'session-test-token');
      assert.equal(init.headers.get('Accept'), 'text/html');
      assert.equal(init.headers.get('Content-Type'), null); // Browser supplies multipart boundary.
      assert.equal(init.body, body);
      assert.equal(init.signal, signal);
      assert.equal(init.credentials, 'same-origin');
      assert.equal(init.mode, 'same-origin');
    }
    assert.equal(dom.window.fetch, originalFetch);
  } finally { dom.window.close(); }
});

test('external destinations and credentials are rejected before sending tokens or form data', () => {
  const { dom, options } = fixture();
  try {
    for (const url of ['https://external.example/save', '//external.example/save', 'http://books.example/save',
      'https://user:pass@books.example/save', 'https://books.example:444/save', 'data:text/plain,no']) {
      assert.throws(() => options(url, { method: 'POST' }));
    }
  } finally { dom.window.close(); }
});

test('GET/PDF carries no CSRF header; missing token fails closed for mutations', () => {
  const { dom, options } = fixture();
  try {
    assert.equal(options('/books/1/export/pdf').headers.get('X-CSRF-Token'), null);
    dom.window.document.querySelector('meta').remove();
    for (const method of ['POST', 'PUT', 'PATCH', 'DELETE']) {
      assert.throws(() => options('/books/preview', { method }), /Recarga/);
    }
  } finally { dom.window.close(); }
});
