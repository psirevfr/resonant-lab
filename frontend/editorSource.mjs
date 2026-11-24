import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {dirname,relative,resolve} from 'node:path';

const range=node=>[node.start,node.end];
const normalize=text=>text?.trim().replace(/\s+/g,' ')??'';
const textTags=/^(?:h[1-6]|b|em|label|li|legend|output|p|small|span|strong|summary|td|th)$/;
const inlineTextTags=/^(?:b|em|small|span|strong)$/;
const anchors=new Set(['id','key','className','name','type','role','data-guide','data-editor-key','aria-label','href','onClick']);
const isText=child=>child.type==='JSXText'&&!!normalize(child.value);

export function readElementStyles(){
 return JSON.parse(readFileSync('src/siteLayout.json','utf8')).elements??{};
}

function labelNodes(node,nested=false){
 const children=node.children??[];
 return children.flatMap(child=>{
  if(isText(child))return [{parent:node,child}];
  if(nested&&child.type==='JSXElement'&&inlineTextTags.test(child.openingElement.name.name??''))return labelNodes(child,true);
  return [];
 });
}

export function editorSource({types:t},{preview=false,elements={}}={}) {
 return {visitor:{
 Program:{
  enter(path,state){
   state.elementCounts=new Map();
   state.textComponent=path.scope.generateUidIdentifier('siteElementText');
  },
  exit(path,state){
   if(!state.usesSiteElementText)return;
   const module=relative(dirname(state.file.opts.filename),resolve('src/SiteElementText'));
   path.unshiftContainer('body',t.importDeclaration([t.importDefaultSpecifier(state.textComponent)],
    t.stringLiteral(module.startsWith('.')?module:'./'+module)));
  },
 },
 JSXElement(element,state){
  const {node,parent}=element;
  const opening=node.openingElement;
  const name=opening?.name;
  if(!opening||typeof name!=='object'||name.type!=='JSXIdentifier'||typeof name.name!=='string'||!(/^[a-z]/.test(name.name)))return;
  const filename=state.file.opts.filename;
  if(!filename)return;
  const path='frontend/'+relative(process.cwd(),filename);
  if(!/^frontend\/src\/[\w./-]+\.[jt]sx$/.test(path))return;
  const isButton=name.name==='button'||name.name==='a';
  const text=labelNodes(node);
  if(!isButton&&!text.length&&!textTags.test(name.name))return;
  const candidates=isButton&&!text.length?labelNodes(node,true):text;
  const literal=candidates.length===1?candidates[0]:undefined;
  const code=state.file.code;
  const signature=start=>[
   start.name?.name,
   ...start.attributes.filter(attr=>attr.type==='JSXAttribute'&&anchors.has(attr.name.name))
    .map(attr=>normalize(code.slice(attr.start,attr.end))).sort(),
  ];
  const parents=[];
  for(let ancestor=element.parentPath;ancestor&&parents.length<6;ancestor=ancestor.parentPath){
   if(ancestor.isJSXElement())parents.unshift(signature(ancestor.node.openingElement));
   if(ancestor.isFunctionDeclaration()||ancestor.isVariableDeclarator()){
    parents.unshift(ancestor.node.id?.name??'');
    break;
   }
  }
  const label=normalize(literal?.child.value);
  const seed=JSON.stringify([path,parents,signature(opening),label]);
  const count=state.elementCounts.get(seed)??0;
  state.elementCounts.set(seed,count+1);
  const id='e-'+createHash('sha256').update(seed+'\0'+count).digest('hex').slice(0,24);
  const style=elements[id];
  if(!preview&&!style)return;
  opening.attributes.push(t.jsxAttribute(t.jsxIdentifier('data-site-element'),t.stringLiteral(id)));
  const setting=path==='frontend/src/LabShell.tsx'&&node.children?.find(child=>child.type==='JSXExpressionContainer'
    &&child.expression.type==='MemberExpression'&&!child.expression.computed
    &&child.expression.object.name==='settings'&&['brandName','signature'].includes(child.expression.property.name))?.expression.property.name;
  const editableLabel=setting?{setting}:literal&&label.length<=240?{text:range(literal.child),label}:{};
  const siblings=parent?.children?.filter(child=>child.type!=='JSXText'||isText(child))??[];
  const index=siblings.indexOf(node);
  const before=index>0?siblings[index-1]:undefined;
  const after=index>=0?siblings[index+1]:undefined;
  if(preview){
   state.revision??=createHash('sha256').update(code).digest('hex');
   const metadata={id,path,revision:state.revision,selected:range(node),button:isButton,...editableLabel,
    before:isButton&&before?.type==='JSXElement'&&Number.isInteger(before.start)?range(before):undefined,
    after:isButton&&after?.type==='JSXElement'&&Number.isInteger(after.start)?range(after):undefined};
   opening.attributes.push(t.jsxAttribute(t.jsxIdentifier('data-editor-source'),t.jsxExpressionContainer(t.stringLiteral(JSON.stringify(metadata)))));
  }
  if(editableLabel.label&&(preview||typeof style.text==='string')){
   const textName=t.jsxIdentifier(state.textComponent.name);
   const children=literal.parent.children;
   children[children.indexOf(literal.child)]=t.jsxElement(
    t.jsxOpeningElement(textName,[t.jsxAttribute(t.jsxIdentifier('id'),t.stringLiteral(id))]),
    t.jsxClosingElement(t.jsxIdentifier(state.textComponent.name)),[literal.child]);
   state.usesSiteElementText=true;
  }
 },
 }};
}
