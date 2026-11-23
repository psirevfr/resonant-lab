import {Component,type ReactNode,lazy,Suspense,useCallback,useEffect,useRef,useState} from 'react';
import {api,resetSession} from './api';
import type {IncomingCircuit} from './circuitProject';
import {Account} from './components/Account';
import {ExportLogin,type LabUser} from './components/ExportLogin';
import type {ComputeJob} from './hooks/useComputeJob';
import {useLearningConsent} from './hooks/useLearningConsent';
import './workspaces.css';
import {LabGuide} from './components/LabGuide';
import type {GuideStep} from './guideContent';
import {APP_VERSION} from './version';
import {useSitePresentation} from './SitePresentation';
import {layoutPage,LayoutContext,pagePath,siteLayout} from './siteLayout';
import {siteSettings,type SiteSpace} from './siteSettings';
const Workshop=lazy(()=>import('./components/ArduinoWorkshop'));
const Audio=lazy(()=>import('./App').then(m=>({default:m.App})));
class WorkspaceBoundary extends Component<{children:ReactNode},{failed:boolean}>{
 state={failed:false};static getDerivedStateFromError(){return {failed:true}}
 render(){return this.state.failed?<div className="workspace-loading" role="alert"><button onClick={()=>location.reload()}>Recharger le laboratoire</button></div>:this.props.children}
}
const currentPage=()=>layoutPage(location.pathname,siteLayout)?.id??siteSettings.home;

export function LabShell(){
 const {settings,layout}=useSitePresentation();
 const editingPreview=import.meta.env.DEV&&window.parent!==window&&new URLSearchParams(location.search).get('editor')==='1';
 const [pageId,setPageId]=useState(currentPage),[audioLoaded,setAudioLoaded]=useState(currentPage()!=='atelier'),[workshopLoaded,setWorkshopLoaded]=useState(currentPage()==='atelier');
 const [menu,setMenu]=useState(false),[user,setUser]=useState<LabUser|null>(null),[login,setLogin]=useState(false),[incoming,setIncoming]=useState<IncomingCircuit|null>(null),[resume,setResume]=useState<ComputeJob|null>(null),[title,setTitle]=useState('Nouveau montage'),[saved,setSaved]=useState(''),[guideTarget,setGuideTarget]=useState('');
 const consent=useLearningConsent(editingPreview?undefined:user?.id);
 const trigger=useRef<HTMLButtonElement>(null),nav=useRef<HTMLDivElement>(null);
 const page=layoutPage(location.pathname,layout)??layout.pages.find(p=>p.id===pageId)??layout.pages.find(p=>p.id===settings.home)??layout.pages[0];
 const name=(id:string)=>layout.pages.find(p=>p.id===id)?.name||settings.labels[id as SiteSpace]||id;
 const nativeWorkshop=page.id==='atelier'&&!page.custom;
 const custom=page.custom?page:undefined;
 const workshopInLayout=!!custom?.blocks.some(b=>b.kind==='workshop');
 const audioActive=!nativeWorkshop;
 useEffect(()=>{api<LabUser>('/me').then(setUser).catch(()=>{})},[]);
 useEffect(()=>{
  const path=location.pathname.replace(/\/$/,'');
  if(path===''||path==='/mon-lab')history.replaceState(null,'',pagePath(settings.home)+location.search);
  const pop=()=>{const next=layoutPage(location.pathname,layout)?.id??settings.home;setPageId(next);if(next==='atelier')setWorkshopLoaded(true);else setAudioLoaded(true)};
  window.addEventListener('popstate',pop);return()=>window.removeEventListener('popstate',pop);
 },[settings.home,layout]);
 const navigate=useCallback((id:string,focus=true)=>{
  setMenu(false);if(focus)trigger.current?.focus();
  if(id==='atelier')setWorkshopLoaded(true);else setAudioLoaded(true);
  if(page.id!==id){document.querySelectorAll('audio').forEach(a=>a.pause());history.pushState(null,'',pagePath(id)+location.search);setPageId(id)}
 },[page.id]);
 useEffect(()=>{
  if(!menu)return;
  nav.current?.querySelector<HTMLAnchorElement>('a[aria-current="page"]')?.focus();
  const key=(e:KeyboardEvent)=>{
   if(e.key==='Escape'){setMenu(false);trigger.current?.focus()}
   if(e.key==='Tab'){const items=[...nav.current!.querySelectorAll<HTMLElement>('a,button')],i=items.indexOf(document.activeElement as HTMLElement);if((e.shiftKey&&i===0)||(!e.shiftKey&&i===items.length-1)){e.preventDefault();items[e.shiftKey?items.length-1:0].focus()}}
  };
  window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);
 },[menu]);
 const guideArea=useCallback((step:GuideStep)=>{navigate(step.space,false);setGuideTarget(step.target)},[navigate]);
 const status=useCallback((value:string,state:string)=>{setTitle(value);setSaved(state)},[]);
 const workshop=(active:boolean)=><Workshop active={active} owner={user?.id} canExport={!!user&&!user.guest} onLogin={()=>setLogin(true)} incoming={incoming} onStatus={status}/>;
 function menuItems(parent:string|null,depth=0):ReactNode{
  if(depth>4)return null;
  return layout.pages.filter(p=>p.parent===parent).map(p=><div key={p.id} className={depth?'layout-subpage':''}><a href={pagePath(p.id)} aria-current={page.id===p.id?'page':undefined} onClick={e=>{e.preventDefault();navigate(p.id)}}>{name(p.id)}</a>{menuItems(p.id,depth+1)}</div>);
 }
 return <LayoutContext.Provider value={layout}><div className="lab-shell" data-editor-key="appearance">
  <header className="lab-topbar"><button ref={trigger} className="lab-menu-button" data-editor-key="navigation" aria-label="Ouvrir le menu des espaces" aria-expanded={menu} aria-controls="space-navigation" onClick={()=>setMenu(v=>!v)}>☰</button><a className="lab-wordmark" data-editor-key="identity" href={pagePath(settings.home)} onClick={e=>{e.preventDefault();navigate(settings.home)}}>{settings.brandName} <span>LAB</span></a><b className="active-space" data-editor-key="navigation">{name(page.id)}</b><span className="shell-project-name">{nativeWorkshop?title:''}</span><small className="shell-save-state">{nativeWorkshop?saved:''}</small><LabGuide autoOpen={!editingPreview&&consent.ready&&(consent.decision!==null||consent.unavailable)} labels={settings.labels} welcome={settings.welcome} userId={user?.id} space={nativeWorkshop?'atelier':'analyse'} onNavigate={navigate} onArea={guideArea}/><Account user={user} onUserChange={setUser} onLogin={()=>setLogin(true)} busy={false} onResume={j=>{setResume(j);navigate('analyse')}}/></header>
  {consent.open&&<section id="learning-consent" className="learning-consent" aria-labelledby="learning-consent-title" aria-busy={consent.saving}>
   <div><h2 id="learning-consent-title">Aider Résonant à s’améliorer</h2><p>Autorisez l’envoi automatique du profil sonore et du score des essais qui améliorent une génération. Le partage exclut vos fichiers audio. Vous pouvez retirer votre accord dans Confidentialité.</p>
   {consent.error&&<p role="alert">{consent.error}</p>}</div>
   <div className="learning-consent-actions"><button type="button" disabled={consent.saving} onClick={()=>void consent.choose('refused')}>{consent.decision==='accepted'?'Retirer mon accord':'Refuser'}</button><button type="button" disabled={consent.saving} onClick={()=>void consent.choose('accepted')}>Accepter</button></div>
  </section>}
  {menu&&<div className="space-menu-backdrop" onPointerDown={e=>{if(e.target===e.currentTarget){setMenu(false);trigger.current?.focus()}}}><div ref={nav} id="space-navigation" className="space-menu" data-editor-key="navigation" role="dialog" aria-modal="true" aria-label="Choisir un espace"><div className="space-menu-title"><button aria-label="Fermer le menu" onClick={()=>{setMenu(false);trigger.current?.focus()}}>×</button></div><nav>{menuItems(null)}</nav></div></div>}
  {login&&<ExportLogin onClose={()=>setLogin(false)} onConnected={u=>{resetSession();setUser(u);setLogin(false)}}/>}
  <main className="workspace-host"><WorkspaceBoundary>
   {workshopLoaded&&!workshopInLayout&&<div className="workshop-space" data-workspace="atelier" hidden={!nativeWorkshop}><Suspense fallback={<p className="workspace-loading">Ouverture de l’atelier…</p>}>{workshop(nativeWorkshop)}</Suspense></div>}
   {(audioLoaded||!!custom)&&<div className="audio-space" data-workspace="analyse" hidden={!audioActive}><Suspense fallback={<p className="workspace-loading">Ouverture de l’analyse…</p>}><Audio layoutPage={custom} onNavigatePage={navigate} extraBlocks={workshopInLayout?{workshop:workshop(audioActive)}:undefined} guideTarget={guideTarget} active={audioActive} accountUser={user} onAccountChange={setUser} learningOwner={consent.decision==='accepted'?user?.id:undefined} resumeJob={resume} onCreateCircuit={(patch,origin)=>{setIncoming(structuredClone({patch,origin}));navigate('atelier')}}/></Suspense></div>}
  </WorkspaceBoundary></main><footer className="site-footer"><span data-editor-key="identity">© {settings.signature}</span>{(consent.unavailable||consent.decision!==null)&&<button className="learning-privacy" type="button" disabled={consent.saving} aria-expanded={consent.open} aria-controls={consent.open?'learning-consent':undefined} onClick={consent.unavailable?consent.reload:consent.toggle}>{consent.unavailable?'Réessayer le choix de confidentialité':'Confidentialité'}</button>}<span>Version {APP_VERSION}</span></footer>
 </div></LayoutContext.Provider>;
}
