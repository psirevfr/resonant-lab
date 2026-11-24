import {createHash} from 'node:crypto';
import {relative} from 'node:path';

const range=node=>[node.start,node.end];

export function editorSource({types:t}) {
 const revisions=new WeakMap();
 return {visitor:{JSXElement({node,parent},state){
  const opening=node.openingElement;
  const name=opening?.name;
  if(!opening||typeof name!=='object'||name.type!=='JSXIdentifier'||typeof name.name!=='string'||!(/^[a-z]/.test(name.name)))return;
  const filename=state.file.opts.filename;
  if(!filename)return;
  const path='frontend/'+relative(process.cwd(),filename);
  if(!/^frontend\/src\/[\w./-]+\.[jt]sx$/.test(path))return;
  const revision=revisions.get(state.file)??createHash('sha256').update(state.file.code).digest('hex');
  revisions.set(state.file,revision);
  const isText=child=>child.type==='JSXText'&&!!child.value?.trim();
  const text=node.children?.filter(isText)??[];
  const siblings=parent?.children?.filter(child=>child.type!=='JSXText'||isText(child))??[];
  const index=siblings.indexOf(node);
  const isButton=name.name==='button'||name.name==='a';
  const before=index>0?siblings[index-1]:undefined;
  const after=index>=0?siblings[index+1]:undefined;
  const label=text.length===1?text[0].value?.trim().replace(/\s+/g,' '):undefined;
  const editableLabel=label&&label.length<=240?{text:range(text[0]),label}:{};
  const metadata={path,revision,selected:range(node),...editableLabel,
   before:isButton&&before?.type==='JSXElement'?range(before):undefined,
   after:isButton&&after?.type==='JSXElement'?range(after):undefined};
  opening.attributes?.push(t.jsxAttribute(t.jsxIdentifier('data-editor-source'),t.jsxExpressionContainer(t.stringLiteral(JSON.stringify(metadata)))));
 }}};
}
