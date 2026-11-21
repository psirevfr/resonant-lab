import test from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {guideSteps} from '../.test-build/guideContent.mjs';
import {siteSettings,mainSpaces,resolveSpace,validateSiteSettings,isLocalEditorOrigin,validateEditorMessage,isEditorKey} from '../.test-build/siteSettings.mjs';

test('Analysis is the main entry, including old Mon Lab links, while explicit workshop links remain supported',()=>{
 assert.deepEqual(mainSpaces,['analyse','atelier']);
 assert.equal(guideSteps[0].space,'analyse');const workshop=guideSteps.findIndex(step=>step.space==='atelier');assert.ok(workshop>0);assert.ok(guideSteps.slice(0,workshop).every(step=>step.space==='analyse'));
 for(const path of ['/','/mon-lab','/mon-lab/','/analyse','/analyse/'])assert.equal(resolveSpace(path,'analyse'),'analyse');
 assert.equal(resolveSpace('/atelier'),'atelier');assert.equal(resolveSpace('/atelier/'),'atelier');
 assert.equal(resolveSpace('/','atelier'),'atelier');
});

test('Presentation validation clones allowed values and rejects extra fields, missing fields and invalid nested structures',()=>{
 const p=structuredClone(siteSettings),before=structuredClone(p),q=validateSiteSettings(p);q.labels.analyse='Écouter';q.colors.accent='#ffeedd';
 assert.deepEqual(p,before);
 for(const change of [p=>delete p.brandName,p=>p.version=2,p=>p.apiKey='not-a-setting',p=>p.labels={analyse:'Son'},p=>p.labels.extra='Unknown',p=>p.colors.extra='#abcdef',p=>p.home='https://example.invalid',p=>p.welcome='\u0000',p=>p.brandName=' ',p=>p.signature='x'.repeat(101),p=>p.labels.analyse='x'.repeat(33),p=>p.welcome='x'.repeat(241)]){
  const p=structuredClone(siteSettings);change(p);assert.throws(()=>validateSiteSettings(p));
 }
 for(const value of [null,[],true,'{}'])assert.throws(()=>validateSiteSettings(value));
});

test('Appearance accepts finite bounded values and plain hex colors, not executable CSS',()=>{
 for(const change of [p=>p.colors.accent='url(https://example.invalid)',p=>p.colors.surface='#fff;display:none',p=>p.fontScale=Infinity,p=>p.fontScale=NaN,p=>p.fontScale=0,p=>p.radius=-1,p=>p.radius=25,p=>p.radius='8px']){
  const p=structuredClone(siteSettings);change(p);assert.throws(()=>validateSiteSettings(p));
 }
 const p=structuredClone(siteSettings);p.fontScale=1.1;p.radius=0;p.colors.accent='#ABC123';assert.equal(validateSiteSettings(p).colors.accent,'#ABC123');
});

test('Editor origin is restricted to canonical HTTP loopback origins',()=>{
 for(const origin of ['http://127.0.0.1','http://127.0.0.1:5173','http://localhost:8483'])assert.equal(isLocalEditorOrigin(origin),true);
 for(const origin of ['null','file://','https://localhost','http://localhost.evil.invalid','http://localhost:5173/path','http://localhost@evil.invalid','http://127.0.0.2:5173','http://[::1]:5173'])assert.equal(isLocalEditorOrigin(origin),false);
});

test('Editor messages require exact payloads and all preview settings are validated',()=>{
 assert.deepEqual(validateEditorMessage({type:'resonant-editor:select-mode',enabled:true}),{type:'resonant-editor:select-mode',enabled:true});
 assert.deepEqual(validateEditorMessage({type:'resonant-editor:preview',settings:siteSettings}).settings,siteSettings);
 for(const value of [{type:'resonant-editor:preview',settings:{}},{type:'resonant-editor:select-mode',enabled:'true'},{type:'resonant-editor:select-mode',enabled:true,command:'delete'},{type:'unknown'},null])assert.throws(()=>validateEditorMessage(value));
 for(const key of ['identity','navigation','appearance','welcome'])assert.equal(isEditorKey(key),true);
 assert.equal(isEditorKey('code'),false);assert.equal(isEditorKey('__proto__'),false);
});

test('Production compilation removes the local editor message handlers',async()=>{
 const result=await build({entryPoints:['src/SitePresentation.tsx'],bundle:true,platform:'browser',format:'esm',write:false,outdir:'.test-build/production-check',minify:true,define:{'import.meta.env.DEV':'false'}});
 const code=result.outputFiles.find(f=>f.path.endsWith('.js'))?.text??result.outputFiles[0].text;
 assert.ok(!/addEventListener\(["']message/.test(code),'production must not listen for editor messages');
 assert.ok(!code.includes('parent.postMessage'),'production must not send editor messages to a parent');
});
