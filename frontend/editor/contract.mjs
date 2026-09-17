import { Marked, Renderer } from 'marked';

export const PAGEBREAK_MARKER = '<!-- pagebreak -->';
export const MAX_DOCUMENT_BYTES = 2 * 1024 * 1024;
export const escapeHtml = (s = '') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const escapeText = (s = '') => String(s).replace(/[&\\`*_{}\[\]()<>#!|~+\-.:]/g, c => `&#${c.charCodeAt(0)};`);
export function safeUrl(value = '') {
  if (/^(?:https?:\/\/|mailto:|#|(?:\.\/)?assets\/)/i.test(value) && !/[\s<>"\x00-\x1f]/.test(value) && !value.split('/').includes('..')) return value;
  throw new Error('Enlace o recurso no compatible. Se conserva el original.');
}
const destination = s => safeUrl(s).replace(/\(/g, '%28').replace(/\)/g, '%29');
const mediaClass = s => (s || 'doc-image doc-align-center doc-w-100').split(/\s+/).filter(c => /^(doc-image|doc-align-(left|right|center)|doc-w-(33|50|66|100))$/.test(c)).join(' ');

// Parse layout before Markdown, but never interpret markers inside a code fence.
export function parseLayout(source) {
  const parts = []; let buffer = [], columns = null, current = [], fence = null;
  const flush = () => { if (buffer.length) parts.push({type:'markdown', text:buffer.join('\n')}); buffer=[]; };
  for (const line of source.split('\n')) {
    const f = line.match(/^\s{0,3}(`{3,}|~{3,})/);
    if (f && (!fence || (f[1][0] === fence[0] && f[1].length >= fence.length))) { fence = fence ? null : f[1]; (columns ? current : buffer).push(line); continue; }
    if (fence) { (columns ? current : buffer).push(line); continue; }
    const start = line.match(/^\s*\[\[columns:([23])\]\]\s*$/i);
    if (start) { if (columns) throw new Error('Columnas anidadas no compatibles.'); flush(); columns={type:'columns',count:Number(start[1]),columns:[]}; continue; }
    if (/^\s*\[\[col\]\]\s*$/i.test(line)) { if (!columns) throw new Error('Separador de columna sin bloque.'); columns.columns.push(current.join('\n')); current=[]; continue; }
    if (/^\s*\[\[\/columns\]\]\s*$/i.test(line)) { if (!columns) throw new Error('Cierre de columnas sin apertura.'); columns.columns.push(current.join('\n')); current=[]; if (columns.columns.length !== columns.count) throw new Error('El número de columnas no coincide; no se descartará texto.'); parts.push(columns); columns=null; continue; }
    if (/^\s*(?:<!--\s*pagebreak\s*-->|\[\[pagebreak\]\])\s*$/i.test(line)) { if (columns) throw new Error('Mueve el salto de página fuera de las columnas.'); flush(); parts.push({type:'pagebreak'}); continue; }
    if (/\[\[(?:\/?columns|col|pagebreak)/i.test(line)) throw new Error('Marcador de maquetación no compatible.');
    (columns ? current : buffer).push(line);
  }
  if (columns || fence) throw new Error('Bloque de columnas o código sin cierre.');
  flush(); return parts;
}

export function prepareDocument(source, resolveAsset = p => p) {
  const warnings = [];
  try {
    if (new TextEncoder().encode(source).length > MAX_DOCUMENT_BYTES) throw new Error('Documento demasiado grande (máximo 2 MB).');
    const parts = parseLayout(source);
    const parser = new Marked({gfm:true, breaks:false});
    parser.use({renderer:{
      image(token) {
        const path = safeUrl(token.href);
        return `<img src="${escapeHtml(resolveAsset(path))}" alt="${escapeHtml(token.text)}" title="${escapeHtml(token.title || '')}" class="${escapeHtml(mediaClass(token.mediaClass))}" data-asset-path="${escapeHtml(path)}">`;
      },
      link(token) { return `<a href="${escapeHtml(safeUrl(token.href))}"${token.title ? ` title="${escapeHtml(token.title)}"` : ''}>${this.parser.parseInline(token.tokens)}</a>`; },
      html(token) {
        const audio = token.text.trim().match(/^<audio\s+controls\s+src="([^"]+)"\s*><\/audio>$/i);
        if (!audio) throw new Error('HTML no compatible con edición visual.');
        const path = safeUrl(audio[1]);
        return `<audio controls data-editor-audio="true" src="${escapeHtml(resolveAsset(path))}" data-asset-path="${escapeHtml(path)}"></audio>`;
      },
      text(token) {
        if (token.tokens) return this.parser.parseInline(token.tokens);
        return new Renderer().text(token).replace(/\[\[worksheet:([A-Za-z0-9_-]+)(?:\|([^\]]+))?\]\]/gi, (_, slug, label) => `<a href="#worksheet-${slug}" data-worksheet-slug="${slug}">${escapeHtml(label || slug)}</a>`);
      },
    }});
    function inspect(tokens) {
      for (let i=0; i<tokens.length; i++) {
        const t=tokens[i];
        if (t.type==='image' && tokens[i+1]?.type==='text') {
          const attrs=tokens[i+1].text.match(/^\{:\s*((?:\.[\w-]+\s*)+)\}/);
          if (attrs) { const value=attrs[1].trim().replace(/\./g,''); if (value !== mediaClass(value)) throw new Error('Atributos de imagen no compatibles.'); t.mediaClass=value; tokens[i+1].text=tokens[i+1].text.slice(attrs[0].length); }
        }
        if (t.type==='def' || (t.type==='list_item' && t.task) || /\[\^|\{[#:]|^---\n[\s\S]*?:/.test(t.type==='code' ? '' : (t.type==='text' ? t.text : ''))) throw new Error('Notas, atributos o tareas no compatibles con edición visual.');
        if (t.type==='image' && /[\[\]\\]/.test(t.text)) throw new Error('Texto alternativo complejo: conserva el original.');
        if (t.tokens) inspect(t.tokens);
        if (t.items) inspect(t.items);
        if (t.type==='table') { for (const cell of [...t.header,...t.rows.flat()]) inspect(cell.tokens); }
      }
    }
    const chunk = text => { const tokens=parser.lexer(text); inspect(tokens); return parser.parser(tokens); };
    const html=parts.map(p => p.type==='pagebreak' ? '<hr data-pagebreak="true">' : p.type==='columns' ? `<div data-layout="columns" data-count="${p.count}">${p.columns.map(c=>`<div data-layout-column="true">${chunk(c) || '<p></p>'}</div>`).join('')}</div>` : chunk(p.text)).join('\n');
    if (/!\[/.test(source)) warnings.push('Las imágenes enlazadas deben existir en la biblioteca; el archivo importado no incluye sus recursos.');
    if (/<table/.test(html)) warnings.push('Tablas simples: comprueba también la lectura y el PDF del servidor.');
    return {ok:true, html, warnings, original:source};
  } catch (error) { return {ok:false, html:'', warnings:[error.message], original:source}; }
}

function inline(nodes=[]) { return nodes.map(serializeNode).join(''); }
function blocks(nodes=[]) { return nodes.map(serializeNode).join('\n\n'); }
function text(node) {
  let value=escapeText(node.text);
  const marks=node.marks || [];
  if (marks.some(m=>m.type==='code')) { const raw=node.text; const fence='`'.repeat(Math.max(0,...[...raw.matchAll(/`+/g)].map(m=>m[0].length))+1); value=fence+((/^`|`$|^ .* $/.test(raw)) ? ` ${raw} ` : raw)+fence; }
  for (const mark of marks) {
    if (mark.type==='code') continue;
    if (['bold','italic','strike'].includes(mark.type)) {
      const delimiter={bold:'**',italic:'*',strike:'~~'}[mark.type];
      value=value.replace(/^(\s*)([\s\S]*?)(\s*)$/, (_,a,b,c)=> b ? a+delimiter+b+delimiter+c : a+c);
    } else if (mark.type==='link') {
      const a=mark.attrs || {};
      if (a.dataWorksheetSlug) { if (!/^[\w-]+$/.test(a.dataWorksheetSlug) || /[\[\]|]/.test(node.text) || marks.length>1) throw new Error('Etiqueta de ficha no compatible.'); value=`[[worksheet:${a.dataWorksheetSlug}|${node.text}]]`; }
      else value=`[${value}](${destination(a.href)}${a.title ? ` "${a.title.replace(/["\\]/g,'\\$&')}"` : ''})`;
    } else throw new Error(`Formato no compatible: ${mark.type}`);
  }
  return value;
}
export function serializeNode(node) {
  const a=node.attrs || {}, c=node.content || [];
  switch(node.type) {
    case 'doc': return blocks(c);
    case 'text': return text(node);
    case 'paragraph': return inline(c);
    case 'heading': return '#'.repeat(a.level || 2)+' '+inline(c);
    case 'hardBreak': return '  \n';
    case 'horizontalRule': return '---';
    case 'pageBreak': return PAGEBREAK_MARKER;
    case 'codeBlock': { const raw=c.map(n=>n.text || '').join(''); const fence='`'.repeat(Math.max(3,...[...raw.matchAll(/`+/g)].map(m=>m[0].length+1))); if (/[\s`]/.test(a.language || '')) throw new Error('Lenguaje de código no compatible.'); return `${fence}${a.language || ''}\n${raw}\n${fence}`; }
    case 'blockquote': return blocks(c).split('\n').map(l=>'> '+l).join('\n');
    case 'bulletList': case 'orderedList': return c.map((item,i)=>{ const prefix=node.type==='bulletList' ? '- ' : `${(a.start || 1)+i}. `; return blocks(item.content).split('\n').map((line,j)=>(j ? ' '.repeat(prefix.length) : prefix)+line).join('\n'); }).join('\n');
    case 'columnsBlock': if (c.length!==Number(a.count)) throw new Error('Número de columnas incorrecto.'); return `[[columns:${a.count}]]\n${c.map(n=>blocks(n.content)).join('\n[[col]]\n')}\n[[/columns]]`;
    case 'image': return `![${escapeText(a.alt || '')}](${destination(a.dataAssetPath || a.src)}${a.title ? ` "${a.title.replace(/["\\]/g,'\\$&')}"` : ''}){: ${mediaClass(a.class).split(' ').map(s=>'.'+s).join(' ')}}`;
    case 'audioBlock': return `<audio controls src="${escapeHtml(safeUrl(a.dataAssetPath || a.src))}"></audio>`;
    case 'table': {
      if (!c.length || !c[0].content?.length) throw new Error('Tabla vacía.');
      const width=c[0].content.length;
      const rows=c.map((row,index)=>{ if(row.content?.length!==width) throw new Error('Tabla irregular.'); return row.content.map(cell=>{ if ((cell.attrs?.colspan || 1)!==1 || (cell.attrs?.rowspan || 1)!==1 || cell.attrs?.colwidth || cell.content?.length!==1 || cell.content[0].type!=='paragraph' || (index===0 ? cell.type!=='tableHeader' : cell.type!=='tableCell')) throw new Error('Solo tablas simples: cabecera, sin combinar celdas ni bloques internos.'); const result=inline(cell.content[0].content); if(result.includes('\n') || /!\[|<audio/.test(result)) throw new Error('La celda solo admite texto en una línea.'); return result; }); });
      return [rows[0],Array(width).fill('---'),...rows.slice(1)].map(r=>'| '+r.join(' | ')+' |').join('\n');
    }
    default: throw new Error(`Bloque no compatible: ${node.type}`);
  }
}
export const serializeDocument = doc => serializeNode(doc);
export function importText(filename, bytes) {
  if (!/\.(md|txt)$/i.test(filename)) throw new Error('Solo .md y .txt. No se importan DOCX ni PDF.');
  if(bytes.byteLength>MAX_DOCUMENT_BYTES) throw new Error('Máximo 2 MB.');
  const raw=new TextDecoder('utf-8',{fatal:true}).decode(bytes);
  const content=/\.txt$/i.test(filename) ? raw.split(/\r?\n/).map(escapeText).join('\n\n') : raw;
  return {...prepareDocument(content), content};
}
