import { generateJSON } from '@tiptap/core';
import { editorExtensions } from './extensions.mjs';
import { prepareDocument, serializeDocument } from './contract.mjs';

// Ignore presentation URLs and editor-only defaults, not document structure.
export function semanticDocument(node) {
  const result = {type:node.type};
  if (node.text !== undefined) result.text=node.text;
  const attrs={...node.attrs};
  if (node.type==='image' || node.type==='audioBlock') { attrs.src=attrs.dataAssetPath || attrs.src; delete attrs.dataAssetPath; }
  for (const key of Object.keys(attrs)) if (attrs[key] == null || ['target','rel'].includes(key)) delete attrs[key];
  if(Object.keys(attrs).length) result.attrs=attrs;
  if(node.marks?.length) result.marks=node.marks.map(semanticDocument).sort((a,b)=>a.type.localeCompare(b.type));
  if(node.content?.length) result.content=node.content.map(semanticDocument);
  return result;
}
export function checkedSerialization(doc) {
  const markdown=serializeDocument(doc);
  const prepared=prepareDocument(markdown);
  if (!prepared.ok) throw new Error(prepared.warnings.join(' '));
  const restored=generateJSON(prepared.html,editorExtensions());
  if(JSON.stringify(semanticDocument(doc)) !== JSON.stringify(semanticDocument(restored))) throw new Error('Este formato no se puede guardar sin cambios. Deshaz la última acción o descarga tu borrador.');
  return markdown;
}
export function loadDocument(source, resolveAsset) {
  const result=prepareDocument(source,resolveAsset);
  if(!result.ok) return result;
  try { checkedSerialization(generateJSON(result.html,editorExtensions())); return result; }
  catch(error) { return {...result,ok:false,html:'',warnings:[...result.warnings,error.message]}; }
}
