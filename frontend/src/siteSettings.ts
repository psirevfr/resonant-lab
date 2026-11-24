import source from './siteSettings.json';
export type SiteSpace='analyse'|'atelier';
export type SiteSettings={version:1;brandName:string;signature:string;home:SiteSpace;labels:Record<SiteSpace,string>;colors:{background:string;surface:string;accent:string;text:string};fontScale:number;radius:number;welcome:string};
export type EditorKey='identity'|'navigation'|'appearance'|'welcome';
export type EditorMessage={type:'resonant-editor:preview';settings:SiteSettings}|{type:'resonant-editor:select-mode';enabled:boolean};

function object(value:unknown,keys:string[]):Record<string,unknown>{
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==keys.length||keys.some(k=>!Object.hasOwn(value,k)))throw Error('Champs de présentation invalides.');
 return value as Record<string,unknown>;
}
function text(value:unknown,max:number):string{
 if(typeof value!=='string'||!value.trim()||value.length>max||/[\u0000-\u001f\u007f]/.test(value))throw Error('Texte de présentation invalide.');
 return value.trim();
}
function range(value:unknown,min:number,max:number):number{
 if(typeof value!=='number'||!Number.isFinite(value)||value<min||value>max)throw Error('Valeur de présentation hors limites.');
 return value;
}
export function validateSiteSettings(value:unknown):SiteSettings{
 const s=object(value,['version','brandName','signature','home','labels','colors','fontScale','radius','welcome']);
 if(s.version!==1||!['analyse','atelier'].includes(s.home as string))throw Error('Version ou accueil de présentation invalide.');
 const labels=object(s.labels,['analyse','atelier']),colors=object(s.colors,['background','surface','accent','text']);
 const color=(value:unknown)=>{if(typeof value!=='string'||!/^#[0-9a-fA-F]{6}$/.test(value))throw Error('Couleur invalide : format #RRGGBB requis.');return value};
 return {version:1,brandName:text(s.brandName,40),signature:text(s.signature,100),home:s.home as SiteSpace,labels:{analyse:text(labels.analyse,32),atelier:text(labels.atelier,32)},colors:{background:color(colors.background),surface:color(colors.surface),accent:color(colors.accent),text:color(colors.text)},fontScale:range(s.fontScale,.9,1.15),radius:range(s.radius,0,18),welcome:text(s.welcome,240)};
}
export const siteSettings=validateSiteSettings(source);
export const mainSpaces=['analyse','atelier'] as const;
export function resolveSpace(pathname:string,home:SiteSpace=siteSettings.home):SiteSpace{
 const path=pathname.replace(/\/$/,'');
 return path==='/atelier'?'atelier':path==='/analyse'?'analyse':home;
}
export function isLocalEditorOrigin(origin:string):boolean{
 try{const url=new URL(origin);return url.protocol==='http:'&&['localhost','127.0.0.1'].includes(url.hostname)&&url.origin===origin}catch{return false}
}
export function validateEditorMessage(value:unknown):EditorMessage{
 if(!value||typeof value!=='object')throw Error('Message éditeur invalide.');
 const message=value as Record<string,unknown>;
 if(message.type==='resonant-editor:preview'){object(value,['type','settings']);return {type:message.type,settings:validateSiteSettings(message.settings)}}
 if(message.type==='resonant-editor:select-mode'){object(value,['type','enabled']);if(typeof message.enabled!=='boolean')throw Error('Mode de sélection invalide.');return {type:message.type,enabled:message.enabled}}
 throw Error('Message éditeur inconnu.');
}
export function isEditorKey(value:unknown):value is EditorKey{return typeof value==='string'&&['identity','navigation','appearance','welcome'].includes(value)}
declare const __RESONANT_VISUAL_EDITOR_ORIGIN__:string;
export const visualEditorOrigin=typeof __RESONANT_VISUAL_EDITOR_ORIGIN__==='string'?__RESONANT_VISUAL_EDITOR_ORIGIN__:'';
