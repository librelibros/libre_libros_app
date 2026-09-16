import { importText, prepareDocument } from './contract.mjs';
import { loadDocument } from './document.mjs';

export function setStatus(form, message) { form._richState.status.textContent = message; }
function download(value, filename, type='text/markdown;charset=utf-8') {
  const url=URL.createObjectURL(new Blob([value],{type}));
  const link=document.createElement('a'); link.href=url; link.download=filename; link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export function initializeIntegrityControls(form, editor) {
  const state=form._richState, input=form.querySelector('[data-editor-input]');
  const toolbar=document.createElement('div'); toolbar.className='actions'; state.status.after(toolbar);
  function button(label, action, editing=false) { const el=document.createElement('button'); el.type='button'; el.className='button button-tonal'; el.textContent=label; el.disabled=editing && state.blocked; el.addEventListener('click',action); toolbar.append(el); return el; }
  button('Descargar borrador',()=>download(input.value,'borrador.md'));
  button('Descargar original',()=>download(state.original,'original.md'));
  button('Rescatar documento visual (JSON)',()=>download(JSON.stringify(editor.getJSON(),null,2),'borrador-editor.json','application/json'));
  button('Deshacer',()=>editor.chain().focus().undo().run(),true);
  button('Rehacer',()=>editor.chain().focus().redo().run(),true);
  button('Lista numerada',()=>editor.chain().focus().toggleOrderedList().run(),true);
  button('Tabla (3 × 3)',()=>editor.chain().focus().insertTable({rows:3,cols:3,withHeaderRow:true}).run(),true);
  button('Añadir fila',()=>editor.chain().focus().addRowAfter().run(),true);
  button('Añadir columna',()=>editor.chain().focus().addColumnAfter().run(),true);
  button('Eliminar tabla',()=>{if(confirm('¿Eliminar la tabla seleccionada? Puedes deshacerlo.')) editor.chain().focus().deleteTable().run();},true);
  const picker=document.createElement('input'); picker.type='file'; picker.accept='.md,.txt'; picker.hidden=true; toolbar.append(picker);
  button('Importar .md/.txt',()=>picker.click(),true);
  picker.addEventListener('change',async()=>{
    const file=picker.files?.[0]; picker.value=''; if(!file) return;
    try {
      const imported=importText(file.name,await file.arrayBuffer());
      const prepared=loadDocument(imported.content);
      if(!prepared.ok) { setStatus(form,'No se ha cambiado el documento. '+prepared.warnings.join(' ')); return; }
      const report=`Importar ${file.name}: ${imported.content.length} caracteres.\n${prepared.warnings.join('\n')}\nSe añadirá al final del borrador; no se publica ni se guarda automáticamente. ¿Continuar?`;
      if(!confirm(report)) return;
      editor.commands.insertContentAt(editor.state.doc.content.size,prepared.html);
      setStatus(form,'Contenido añadido al borrador. Revísalo en Edición y Lectura antes de guardar. Puedes deshacer la importación.');
    } catch(error) { setStatus(form,'No se ha importado: '+error.message); }
  });
  window.addEventListener('beforeunload',event=>{if(state.dirty && !state.savedNavigation){event.preventDefault();event.returnValue='';}});
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    if(state.invalid || state.saving) {setStatus(form,'No se puede guardar todavía: revisa el formato.');return;}
    // Require every local resource referenced by the draft to exist or be queued.
    const known=new Set([...state.transfer.files].map(f=>`assets/${f.name}`));
    form.querySelectorAll('[data-asset-filename]').forEach(b=>known.add(`assets/${b.dataset.assetFilename}`));
    const prepared=prepareDocument(input.value);
    if(prepared.ok) {
      const fragment=new DOMParser().parseFromString(prepared.html,'text/html');
      const missing=[...fragment.querySelectorAll('[data-asset-path]')].map(n=>n.getAttribute('data-asset-path').replace(/^\.\//,'')).filter(p=>p.startsWith('assets/') && !known.has(p));
      if(missing.length && state.dirty){setStatus(form,'Faltan recursos: '+[...new Set(missing)].join(', ')+'. Añádelos o quita sus referencias antes de guardar.');return;}
    }
    state.saving=true;
    editor.setEditable(false, false);
    const buttons=[...form.querySelectorAll('button')].map(b=>[b,b.disabled]);
    buttons.forEach(([b])=>{b.disabled=true;});
    setStatus(form,'Guardando… No cierres esta página.');
    try {
      const response=await fetch(form.action,window.LibreLibrosCSRF.options(form.action,{method:'POST',body:new FormData(form),headers:{Accept:'text/html'}}));
      const url=new URL(response.url,window.location.href);
      if(!response.ok || !response.redirected || url.origin!==window.location.origin || !url.pathname.startsWith('/books/') || url.searchParams.has('error')) throw new Error(`HTTP ${response.status}`);
      state.savedNavigation=true;
      state.dirty=false;
      window.location.assign(url.href);
    } catch(error) {
      setStatus(form,'No se pudo confirmar el guardado. Tu borrador y archivos siguen aquí. Comprueba la conexión/sesión y reintenta; si hubo un corte, revisa primero si el servidor guardó los cambios.');
    } finally {
      state.saving=false;
      editor.setEditable(!state.blocked, false);
      buttons.forEach(([b,disabled])=>{b.disabled=disabled;});
    }
  });
}
