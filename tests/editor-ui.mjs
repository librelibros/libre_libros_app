import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {JSDOM} from 'jsdom';
const bundle=readFileSync(new URL('../app/static/js/editor-rich.js',import.meta.url),'utf8');
function mount(source) {
  const dom=new JSDOM(`<form method="post" action="/books/1/edit" data-rich-markdown-editor><input type="hidden" name="content" data-editor-input><input name="branch_name" value="main" data-branch-label="Material base"><input data-editor-book-id value="1"><input data-editor-branch value="main"><input type="file" data-asset-input><div data-rich-editor></div><div data-rich-preview></div><button type="button" data-rich-mode-button="preview">Lectura</button><button type="button" data-open-save-dialog>Guardar</button><dialog data-save-dialog><button type="submit">Guardar cambios</button></dialog><div data-save-branch></div></form>`,{url:'https://example.test/books/1/edit',runScripts:'outside-only',pretendToBeVisual:true});
  const w=dom.window;
  w.TextEncoder=TextEncoder; w.TextDecoder=TextDecoder;
  w.DataTransfer=class { constructor(){this.files=[];this.items={add:f=>this.files.push(f)};} };
  Object.defineProperty(w.HTMLInputElement.prototype,'files',{configurable:true,get(){return this._files || [];},set(v){this._files=v;}});
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
  w.HTMLDialogElement.prototype.close=function(){this.open=false;};
  w.fetch=async()=>{throw new Error('offline');};
  const form=w.document.querySelector('form');form.querySelector('[data-editor-input]').value=source;
  w.eval(bundle);w.document.dispatchEvent(new w.Event('DOMContentLoaded'));
  return {dom,w,form,state:form._richState,input:form.querySelector('[data-editor-input]')};
}
test('real initializer preserves CRLF and opens Ctrl+S once; editing and undo are safe',async()=>{
  const s='# Título\r\n\r\nTexto.\r\n';const {dom,w,form,state,input}=mount(s);
  assert.equal(input.value,s);assert.equal(form.querySelector('[data-save-branch]').textContent,'Material base');
  w.document.dispatchEvent(new w.KeyboardEvent('keydown',{key:'s',ctrlKey:true,bubbles:true}));
  w.document.dispatchEvent(new w.KeyboardEvent('keydown',{key:'s',ctrlKey:true,bubbles:true}));
  assert.equal(form.querySelector('dialog').open,true);
  state.editor.commands.insertContentAt(2,'nuevo ');assert.equal(state.dirty,true);assert.equal(state.invalid,false);
  state.editor.commands.undo();assert.equal(input.value,s);assert.equal(state.dirty,false);
  dom.window.close();
});
test('malformed document is visible readonly and exact original remains',()=>{
  const source='[[columns:2]]\nNo perder';const {dom,form,state,input}=mount(source);
  assert.equal(state.blocked,true);assert.equal(input.value,source);assert.equal(form.querySelector('textarea').value,source);
  dom.window.close();
});
test('preview failure and save failure keep draft, dirty state and retry enabled',async()=>{
  const {dom,w,form,state,input}=mount('Hola');
  state.editor.commands.insertContentAt(2,'nuevo'); const value=input.value;
  form.querySelector('[data-rich-mode-button]').click();await new Promise(r=>setTimeout(r,10));
  assert.match(state.status.textContent,/No se pudo actualizar/);
  form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await new Promise(r=>setTimeout(r,10));
  assert.equal(input.value,value);assert.equal(state.dirty,true);assert.equal(state.saving,false);assert.match(state.status.textContent,/No se pudo confirmar/);
  const event=new w.Event('beforeunload',{cancelable:true});w.dispatchEvent(event);assert.equal(event.defaultPrevented,true);
  dom.window.close();
});
