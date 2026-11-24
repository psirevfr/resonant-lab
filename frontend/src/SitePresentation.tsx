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
  if(import.meta.env.DEV){
  if(window.parent===window||!isLocalEditorOrigin(visualEditorOrigin)||location.hostname!=='127.0.0.1')return;
  const parentOrigin=visualEditorOrigin;
  let selecting=false,sourceMode=false;
  window.parent.postMessage({type:'resonant-editor:ready'},parentOrigin);
  const receive=(event:MessageEvent)=>{
   if(event.source!==window.parent||event.origin!==parentOrigin)return;
   try{
    if(event.data?.type==='resonant-editor:source-mode'&&typeof event.data.enabled==='boolean'){
     sourceMode=event.data.enabled;
     document.documentElement.toggleAttribute('data-editor-source-mode',sourceMode);
     return;
    }
    if(event.data?.type==='resonant-editor:layout'){
     const incoming=event.data.layout as SiteLayout;
     if(incoming?.version===1&&Array.isArray(incoming.pages)&&incoming.pages.length<=24&&incoming.plots&&Array.isArray(incoming.bank))setLayout(incoming);
     return;
    }
    const message=validateEditorMessage(event.data);
    if(message.type==='resonant-editor:preview')setSettings(message.settings);
    else{selecting=message.enabled;document.documentElement.toggleAttribute('data-editor-select-mode',selecting)}
   }catch{/* Reject malformed previews without altering the current site. */}
  };
  const cleanupDrag=createEditorDrag(()=>selecting&&!sourceMode,move=>{
   window.parent.postMessage({type:'resonant-editor:move',...move},parentOrigin);
  });
  const blockPointer=(event:PointerEvent)=>{if(selecting&&event.target instanceof Element&&event.target.closest('[data-editor-key]')){event.preventDefault();event.stopImmediatePropagation()}};
  const select=(event:MouseEvent)=>{
   if(!selecting||!(event.target instanceof Element))return;
   if(sourceMode){openSource(event);return;}
   const block=event.target.closest<HTMLElement>('[data-layout-block]')?.dataset.layoutBlock;
   if(block){event.preventDefault();event.stopImmediatePropagation();window.parent.postMessage({type:'resonant-editor:block',id:block},parentOrigin);return;}
   const key=event.target.closest<HTMLElement>('[data-editor-key]')?.dataset.editorKey;
   if(!isEditorKey(key))return;
   event.preventDefault();event.stopImmediatePropagation();window.parent.postMessage({type:'resonant-editor:selected',key},parentOrigin);
  };
  const openSource=(event:MouseEvent)=>{
   if(!selecting||!(event.target instanceof Element))return;
   const element=event.target.closest<HTMLElement>('button[data-editor-source],a[data-editor-source]')
      ??event.target.closest<HTMLElement>('[data-editor-source]');
   if(!element?.dataset.editorSource)return;
   event.preventDefault();event.stopImmediatePropagation();
   window.parent.postMessage({type:'resonant-editor:source',metadata:element.dataset.editorSource},parentOrigin);
  };
  window.addEventListener('message',receive);document.addEventListener('pointerdown',blockPointer,true);document.addEventListener('click',select,true);
  return()=>{cleanupDrag();window.removeEventListener('message',receive);document.removeEventListener('pointerdown',blockPointer,true);document.removeEventListener('click',select,true);document.documentElement.removeAttribute('data-editor-select-mode');document.documentElement.removeAttribute('data-editor-source-mode')};
  }
 },[]);
 return {settings,layout};
}
