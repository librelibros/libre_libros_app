import { test } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { generateJSON } from '@tiptap/core';
import { prepareDocument, serializeDocument, importText } from '../frontend/editor/contract.mjs';
import { editorExtensions } from '../frontend/editor/extensions.mjs';
import { loadDocument, checkedSerialization, semanticDocument } from '../frontend/editor/document.mjs';
const dom=new JSDOM('<!doctype html><body></body>');
Object.assign(globalThis,{window:dom.window,document:dom.window.document,DOMParser:dom.window.DOMParser});
const json = html => generateJSON(html,editorExtensions());
for (const source of [
  '# Español áéíóú ñ ¿sí?\n\nTexto **fuerte** y ~~tachado~~ con `código`.',
  '5. Cinco\n6. Seis\n   - sublista',
  '```python\nprint("á")\n# no título\n```',
  '| Uno | Dos |\n| --- | --- |\n| á \\| b | **ñ** |',
  '[[columns:3]]\nA\n[[col]]\nB\n[[col]]\nC\n[[/columns]]',
  '<!-- PAGEBREAK -->\n\nSegunda',
  '![Portada](assets/cover.svg){: .doc-image .doc-align-right .doc-w-50}',
  '[[worksheet:ficha|Actividad]]',
]) test('round-trip '+source.slice(0,45),()=>{
  const prepared=loadDocument(source); assert.equal(prepared.ok,true,prepared.warnings.join(' '));
  const doc=json(prepared.html); const md=checkedSerialization(doc);
  assert.deepEqual(semanticDocument(json(prepareDocument(md).html)),semanticDocument(doc));
});
test('literal text is escaped rather than interpreted',()=>{
  const doc={type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'[literal](https://example.org) *a* <tag> 1. Ñ | x'}]}]};
  assert.deepEqual(semanticDocument(json(prepareDocument(checkedSerialization(doc)).html)),semanticDocument(doc));
});
for(const source of ['[[columns:2]]\ntexto importante','[[columns:2]]\nA\n[[col]]\nB\n[[col]]\nC\n[[/columns]]','<iframe>no</iframe>','- [x] tarea']) test('blocked source preserved '+source.slice(0,35),()=>{const p=loadDocument(source);assert.equal(p.ok,false);assert.equal(p.original,source);});
test('code fence does not interpret page/column markers',()=>{assert.equal(loadDocument('```\n[[columns:2]]\n<!-- pagebreak -->\n```').ok,true);});
test('unknown schema node fails closed',()=>{assert.throws(()=>serializeDocument({type:'doc',content:[{type:'unknown',content:[]}]}));});
test('imports only explicit formats and literal txt',()=>{
  const bytes=new TextEncoder().encode('# literal á');
  assert.throws(()=>importText('doc.pdf',bytes));
  assert.equal(json(importText('doc.txt',bytes).html).content[0].type,'paragraph');
  assert.throws(()=>importText('doc.md',new Uint8Array([255])));
});
