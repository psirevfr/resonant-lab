/// <reference types="vite/client" />
import {useEffect,useState} from 'react';
import {isEditorKey,isLocalEditorOrigin,siteSettings,validateEditorMessage,visualEditorOrigin} from './siteSettings';
import './sitePresentation.css';
import {siteLayout,type SiteLayout} from './siteLayout';
import {createEditorDrag} from './editorDrag';

export function useSitePresentation(){
 const [settings,setSettings]=useState(siteSettings),[layout,setLayout]=useState(siteLayout);
 // Source edits from the local visual editor also apply after Vite hot reload.
 useEffect(()=>setSettings(siteSettings),[siteSettings]);
 useEffect(()=>setLayout(siteLayout),[siteLayout]);
 useEffect(()=>{
  const root=document.documentElement;
  const values={'--site-background':settings.colors.background,'--site-surface':settings.colors.surface,'--site-accent':settings.colors.accent,'--site-text':settings.colors.text,'--site-font-scale':String(settings.fontScale),'--site-radius':settings.radius+'px','--green':settings.colors.accent};
  const previous=Object.fromEntries(Object.keys(values).map(key=>[key,root.style.getPropertyValue(key)]));
  for(const [key,value] of Object.entries(values))root.style.setProperty(key,value);
  return()=>{for(const [key,value] of Object.entries(previous)){if(value)root.style.setProperty(key,value);else root.style.removeProperty(key)}};
 },[settings]);
 useEffect(()=>{
  const rules=Object.entries(layout.elements??{}).flatMap(([id,style])=>{
   if(!/^e-[a-f0-9]{24}$/.test(id)||!style)return [];
   const color=/^#[0-9a-f]{6}$/i;
   const declarations=[];
   if(style.color&&color.test(style.color))declarations.push(`color:${style.color} !important`);
   if(style.background&&color.test(style.background))declarations.push(`background-color:${style.background} !important`);
   return declarations.length?[`[data-site-element="${id}"]:not([data-editor-default-style]){${declarations.join(';')}}`]:[];
  });
  if(!rules.length)return;
  const sheet=document.createElement('style');
  sheet.textContent=rules.join('\n');
  document.head.append(sheet);
  return()=>sheet.remove();
 },[layout.elements]);
 useEffect(()=>{
  if(import.meta.env.DEV){
  if(window.parent===window||!isLocalEditorOrigin(visualEditorOrigin)||location.hostname!=='127.0.0.1')return;
  const parentOrigin=visualEditorOrigin;
  let selecting=false,selection:HTMLElement|undefined;
  const mark=(element?:HTMLElement)=>{
   selection?.removeAttribute('data-editor-selection');
   selection=element;
   selection?.setAttribute('data-editor-selection','');
  };
  window.parent.postMessage({type:'resonant-editor:ready'},parentOrigin);
  const receive=(event:MessageEvent)=>{
   if(event.source!==window.parent||event.origin!==parentOrigin)return;
   try{
    if(event.data?.type==='resonant-editor:layout'){
     const incoming=event.data.layout as SiteLayout;
     if(incoming?.version===1&&Array.isArray(incoming.pages)&&incoming.pages.length<=24&&incoming.plots&&Array.isArray(incoming.bank))setLayout(incoming);
     return;
    }
    const message=validateEditorMessage(event.data);
    if(message.type==='resonant-editor:preview')setSettings(message.settings);
    else{selecting=message.enabled;document.documentElement.toggleAttribute('data-editor-select-mode',selecting);if(!selecting)mark();}
   }catch{/* Reject malformed previews without altering the current site. */}
  };
  const cleanupDrag=createEditorDrag(()=>selecting,move=>{
   window.parent.postMessage({type:'resonant-editor:move',...move},parentOrigin);
  });
  const blockPointer=(event:PointerEvent)=>{if(selecting&&event.target instanceof Element&&event.target.closest('[data-editor-key]')){event.preventDefault();event.stopImmediatePropagation()}};
  const select=(event:MouseEvent)=>{
   if(!selecting||!(event.target instanceof Element))return;
   const group=event.target.closest<HTMLElement>('[data-layout-block]')??undefined;
   const block=group?.dataset.layoutBlock;
   const button=event.target.closest<HTMLElement>('button[data-editor-source],a[data-editor-source]');
   const element=button??event.target.closest<HTMLElement>('[data-editor-source]');
   if(block&&['text','link','image'].includes(group?.dataset.layoutKind??'')){
    event.preventDefault();event.stopImmediatePropagation();mark(group);
    window.parent.postMessage({type:'resonant-editor:block',id:block},parentOrigin);return;
   }
   if(element?.dataset.editorSource){
    event.preventDefault();event.stopImmediatePropagation();mark(element);
    element.setAttribute('data-editor-default-style','');
    const {color,backgroundColor}=getComputedStyle(element);
    element.removeAttribute('data-editor-default-style');
    const id=element.dataset.siteElement;
    const shared=!!id&&/^e-[a-f0-9]{24}$/.test(id)&&document.querySelectorAll(`[data-site-element="${id}"]`).length>1;
    window.parent.postMessage({type:'resonant-editor:source',metadata:element.dataset.editorSource,
     color,background:backgroundColor,block,shared},parentOrigin);return;
   }
   if(block){
    event.preventDefault();event.stopImmediatePropagation();mark(group);
    window.parent.postMessage({type:'resonant-editor:block',id:block},parentOrigin);return;
   }
   const key=event.target.closest<HTMLElement>('[data-editor-key]')?.dataset.editorKey;
   if(!isEditorKey(key))return;
   event.preventDefault();event.stopImmediatePropagation();window.parent.postMessage({type:'resonant-editor:selected',key},parentOrigin);
  };
  const selectDisabled=(event:PointerEvent)=>{
   if(event.button===0&&event.target instanceof Element&&event.target.closest('button:disabled'))select(event);
  };
  window.addEventListener('message',receive);document.addEventListener('pointerdown',blockPointer,true);
  document.addEventListener('click',select,true);document.addEventListener('pointerup',selectDisabled,true);
  return()=>{cleanupDrag();mark();window.removeEventListener('message',receive);document.removeEventListener('pointerdown',blockPointer,true);document.removeEventListener('click',select,true);document.removeEventListener('pointerup',selectDisabled,true);document.documentElement.removeAttribute('data-editor-select-mode')};
  }
 },[]);
 return {settings,layout};
}
