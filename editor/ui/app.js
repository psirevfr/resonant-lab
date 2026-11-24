'use strict';
const $=selector=>document.querySelector(selector),all=selector=>[...document.querySelectorAll(selector)],token=$('meta[name="editor-token"]').content;
$('meta[name="editor-token"]').remove();
let draft=null,saved=null,state=null,layout=null,savedLayout=null,undo=[],redo=[],lastChange=null,section='insert',gridMode=false,previewDeadline=0,page='analyse',selectMode=true,previewOrigin='',previewReady=false,previewTimer=0,requesting=false,lastJobId='',lastStatus='',dirty=false,device='desktop';
let sourceMode=false;
let diskRevision=null,editorRevision=null,restartAt=0,previousReady=false,previewBusy=false;
const clone=v=>JSON.parse(JSON.stringify(v));
const canonical=v=>JSON.stringify(v,(_,item)=>item&&typeof item==='object'&&!Array.isArray(item)?Object.keys(item).sort().reduce((o,k)=>(o[k]=item[k],o),{}):item);
const same=(a,b)=>canonical(a)===canonical(b);
function showMessage(text,error=false){$('#banner').textContent=text;$('#banner').classList.toggle('error',error);$('#banner').hidden=!text;}
async function api(path,body){const response=await fetch(path,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers:{'X-Editor-Token':token,...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});let result;try{result=await response.json()}catch{throw Error('La réponse de l’éditeur est illisible.')}if(!response.ok)throw Object.assign(Error(result.error||result.detail||'Cette action n’a pas abouti.'),{status:response.status});return result;}
function get(obj,path){return path.split('.').reduce((o,k)=>o?.[k],obj);}
function set(obj,path,value){const keys=path.split('.'),last=keys.pop();keys.reduce((o,k)=>o[k],obj)[last]=value;}
function busy(){return requesting||['running','preparing','publishing'].includes(state?.job?.status);}
function refresh(){if(!draft)return;dirty=!same(draft,saved)||!same(layout,savedLayout);$('#save-status').textContent=busy()?'Vérification en cours…':dirty?'Modifications non enregistrées':'Enregistré sur ce Mac';$('#save').disabled=busy()||!dirty;$('#prepare').disabled=busy();$('#publish').disabled=busy();$('#undo').disabled=!undo.length||busy();$('#redo').disabled=!redo.length||busy();$('#preview-page').textContent=layout?.pages.find(p=>p.id===page)?.name||draft.labels[page]||page;$('#font-value').textContent=Math.round(draft.fontScale*100)+' %';$('#radius-value').textContent=draft.radius+' px';all('[data-setting]').forEach(input=>{input.disabled=busy();const value=get(draft,input.dataset.setting);if(document.activeElement!==input)input.value=String(value);});}
function sendPreview(){clearTimeout(previewTimer);previewTimer=setTimeout(()=>{if(!draft||!previewReady||!previewOrigin)return;const frame=$('#preview');frame.contentWindow?.postMessage({type:'resonant-editor:preview',settings:draft},previewOrigin);if(layout)frame.contentWindow?.postMessage({type:'resonant-editor:layout',layout},previewOrigin);frame.contentWindow?.postMessage({type:'resonant-editor:source-mode',enabled:sourceMode},previewOrigin);frame.contentWindow?.postMessage({type:'resonant-editor:select-mode',enabled:selectMode},previewOrigin);},80);}
function edit(path,value){if(!draft||busy())return;const now=Date.now();if(!lastChange||lastChange.path!==path||now-lastChange.time>750){undo.push(snapshot());if(undo.length>50)undo.shift();}lastChange={path,time:now};redo=[];set(draft,path,value);refresh();sendPreview();}
function snapshot(){return {draft:clone(draft),layout:clone(layout),page,selectedBlock};}
function restore(snapshot){
 const previous=page;
 draft=snapshot.draft;layout=snapshot.layout;page=snapshot.page;selectedBlock=snapshot.selectedBlock;
 renderLayout();if(previous!==page)setPage(page);
}
const panelNames={appearance:'Thèmes',identity:'Textes et identité',navigation:'Pages',welcome:'Aide de Rémi',layout:'Bloc sélectionné',insert:'Insérer',bank:'Banque',plots:'Graphiques',terminal:'Console'};
function showSection(key){
 if(!Object.hasOwn(panelNames,key))return;
 section=key;
 all('[data-section]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.section===key)));
 all('[data-panel]').forEach(panel=>panel.hidden=panel.dataset.panel!==key);
 $('#panel-title').textContent=panelNames[key];
 $('#panel-title').hidden=['insert','navigation','appearance','terminal'].includes(key);
 $('#panel-menu').open=false;
 renderLayout();
}
function showGrid(enabled){
 gridMode=enabled;
 $('#grid-mode').setAttribute('aria-pressed',String(enabled));
 renderLayout();
 if(!enabled)sendPreview();
}
function resizePreview(){
 const stage=$('.preview-stage'),frame=$('.preview-frame'),shell=$('.preview-viewport');
 const available=Math.max(180,stage.clientWidth-16),width={desktop:Math.max(1024,available),tablet:768,mobile:390}[device];
 const scale=Math.min(1,available/width),height=Math.max(220,stage.clientHeight-16);
 frame.style.width=width+'px';frame.style.height=(height/scale)+'px';frame.style.transform='scale('+scale+')';
 shell.style.width=(width*scale)+'px';shell.style.height=height+'px';
}
function setPreviewStatus(message,retry=false){
 $('#preview-status').textContent=message;
 $('#preview-retry').hidden=!retry;
 $('#preview-loading').hidden=!message||gridMode;
}
function setPage(next){
 page=next;
 refresh();renderLayout();
 if(!state?.previewUrl)return;
 const url=new URL(state.previewUrl);
 url.pathname=['analyse','atelier'].includes(next)?'/'+next:'/p/'+next;
 url.searchParams.set('editor','1');
 previewReady=false;previewBusy=false;
 setPreviewStatus('Ouverture du site local…');
 clearTimeout(previewDeadline);
 previewDeadline=setTimeout(()=>setPreviewStatus('La page locale ne répond pas.',true),18000);
 $('#preview').src=url.href;
}
function showActivity(value){$('#activity').hidden=!value;$('#log-toggle').setAttribute('aria-expanded',String(value));}
function updateJob(job){
 if(!job)return;
 if(previousReady&&!job.readyToPublish&&job.status!=='running'&&!job.publication)showMessage('Le projet a été actualisé. La vérification peut être relancée.');
 previousReady=job.readyToPublish;
 const log=Array.isArray(job.log)?job.log.join('\n'):job.log||'';
 if($('#activity-log').textContent!==log){$('#activity-log').textContent=log;$('#activity-log').scrollTop=$('#activity-log').scrollHeight;}
 const actions=$('#deployment-actions');
 actions.hidden=!job.publication;
 if(job.publication)actions.href=job.publication.actionsUrl;
 if(job.id===lastJobId&&job.status===lastStatus)return;
 if(job.status==='failed')showMessage(job.error||'L’opération a échoué. Consultez le suivi.',true);
 if(job.readyToPublish)showMessage('Version vérifiée. Vous pouvez la publier.');
 if(job.publication)showMessage('Version '+job.publication.commit+' reçue par GitHub. Suivez la mise en ligne dans GitHub Actions.');
 if(job.stage==='Déjà à jour')showMessage('GitHub possède déjà cette version.');
 lastJobId=job.id;lastStatus=job.status;
}
function synchronizePresentation(next){
 if(!next.presentationRevision||diskRevision===next.presentationRevision)return;
 const before=page;
 if(draft){
  const rebase=item=>({...item,
   draft:mergePresentation(saved,item.draft,next.settings),
   layout:mergePresentation(savedLayout,item.layout,next.layout)});
  undo=undo.map(rebase);redo=redo.map(rebase);
  const merged=rebase({draft,layout});
  draft=merged.draft;layout=merged.layout;lastChange=null;
 }else{
  draft=clone(next.settings);layout=clone(next.layout);page=draft.home;
 }
 saved=clone(next.settings);savedLayout=clone(next.layout);diskRevision=next.presentationRevision;
 if(!layout.pages.some(item=>item.id===page))page=draft.home;
 if(page!==before&&previewOrigin)setPage(page);else renderLayout();
 refresh();sendPreview();
}
async function poll(){
 try{
  const payload=draft?await api('/api/progress'):await api('/api/state');
  state={...state,...payload};
  if(restartAt&&editorRevision!==state.editorRevision){location.reload();return;}
  editorRevision=state.editorRevision;
  if(!draft)synchronizePresentation(state);
  else if(!requesting&&state.presentationRevision&&state.presentationRevision!==diskRevision)
   synchronizePresentation(await api('/api/state'));
  if(state.editorChanged&&draft&&!busy()&&!dirty&&!previewBusy&&!window.resonantSourceDirty?.()&&!document.querySelector('dialog[open]')&&!restartAt){
   restartAt=Date.now();
   showMessage('Actualisation de l’éditeur…');
   try{await api('/api/restart',{});}catch(error){restartAt=0;throw error;}
  }
  if(state.previewUrl&&!previewOrigin){
   const url=new URL(state.previewUrl);
   if(url.hostname!=='127.0.0.1'||url.protocol!=='http:')throw Error('Adresse d’aperçu local invalide.');
   previewOrigin=url.origin;
   $('#preview').hidden=false;
   setPage(page);
  }
  if(state.previewError)setPreviewStatus(state.previewError,true);
  updateJob(state.job);refresh();
 }catch(e){if(!restartAt||Date.now()-restartAt>20000){restartAt=0;showMessage(e.message,true);}}
 setTimeout(poll,busy()?1000:2000);
}
async function save(){
 if(!draft)return;
 let result;
 for(let attempt=0;attempt<2;attempt++){
  try{
   result=await api('/api/save',{settings:draft,layout,revision:diskRevision});
   break;
  }catch(error){
   if(error.status!==409||attempt)throw error;
   synchronizePresentation(await api('/api/state'));
  }
 }
 draft=clone(result.settings);layout=clone(result.layout);
 saved=clone(result.settings);savedLayout=clone(result.layout);diskRevision=result.presentationRevision;
 showMessage('Présentation enregistrée.');lastChange=null;refresh();sendPreview();
}
all('[data-setting]').forEach(input=>input.addEventListener('input',()=>{let value=input.value;const path=input.dataset.setting;if(path==='fontScale'||path==='radius')value=Number(value);if(path.startsWith('colors.')&&!/^#[0-9a-f]{6}$/i.test(value))return;edit(path,value);}));
all('[data-section]').forEach(b=>b.addEventListener('click',()=>showSection(b.dataset.section)));
all('[data-device]').forEach(b=>b.addEventListener('click',()=>{all('[data-device]').forEach(v=>v.setAttribute('aria-pressed',String(v===b)));device=b.dataset.device;$('.preview-frame').className='preview-frame '+device;resizePreview();$('#preview-menu').open=false;showGrid(false);}));
all('[data-preset]').forEach(b=>b.addEventListener('click',()=>{const colors={original:{background:'#111719',surface:'#18201f',accent:'#b4ed79',text:'#dbe4e5'},ocean:{background:'#111a20',surface:'#172a33',accent:'#81d4e8',text:'#e0edf1'},violet:{background:'#17151e',surface:'#24202e',accent:'#c6b5ff',text:'#e9e3f3'}}[b.dataset.preset];edit('colors',colors);}));
$('#undo').onclick=()=>{if(!undo.length||busy())return;redo.push(snapshot());restore(undo.pop());lastChange=null;refresh();sendPreview();};
$('#redo').onclick=()=>{if(!redo.length||busy())return;undo.push(snapshot());restore(redo.pop());lastChange=null;refresh();sendPreview();};
$('#save').onclick=async()=>{try{requesting=true;refresh();await save();}catch(e){showMessage(e.message,true);}finally{requesting=false;refresh();}};
let publicationReview=null;
async function openReview(action){
 if(!draft||busy())return;
 const dialog=$('#review-dialog'),message=$('#review-summary');
 const publishing=action==='publish';
 publicationReview=null;$('#run-review').disabled=true;$('#review-details').hidden=true;
 $('#review-title').textContent=publishing?'Publier la version complète':'Vérification';
 $('#run-review').textContent=publishing?'Publier sur GitHub':'Vérifier la version locale';
 message.textContent=dirty?'Enregistrement des réglages…':'Lecture des changements locaux…';
 dialog.showModal();
 try{
  requesting=true;refresh();
  if(dirty)await save();
  const details=await api('/api/publication-review');
  if(!dialog.open)return;
  publicationReview={review:details.review,action};
  const scope=details.count+' commits locaux · '+details.localCount+' fichiers modifiés.';
  message.textContent=scope+(publishing?' Après les contrôles, la version complète sera envoyée sur main et déclenchera le déploiement du site.':' Les tests et la compilation seront vérifiés sur ce Mac.');
  const list=details.paths.map(path=>{const item=document.createElement('li');item.textContent=path;return item;});
  $('#review-files').replaceChildren(...list);
  $('#review-details').hidden=!list.length;
  $('#review-details').open=details.paths.some(path=>path.startsWith('.github/workflows/'));
  $('#run-review').disabled=false;
 }catch(error){message.textContent=error.message;}
 finally{requesting=false;refresh();}
}
$('#prepare').onclick=()=>openReview('prepare');
$('#publish').onclick=()=>openReview('publish');
$('#cancel-review').onclick=()=>$('#review-dialog').close();
$('#run-review').onclick=async()=>{
 if(!publicationReview||busy())return;
 const {review,action}=publicationReview;
 $('#review-dialog').close();
 try{
  requesting=true;refresh();showActivity(true);
  showMessage(action==='publish'?'Préparation de la publication complète…':'Vérification des fichiers, des tests et de la compilation…');
  state.job=(await api('/api/'+action,{review})).job;
  updateJob(state.job);
 }catch(error){showMessage(error.message,true);}
 finally{requesting=false;refresh();}
};
function changeMode(enabled,source=false){
 selectMode=enabled;sourceMode=source;
 $('#select-mode').setAttribute('aria-pressed',String(enabled&&!source));
 $('#source-mode').setAttribute('aria-pressed',String(source));
 $('#browse-mode').setAttribute('aria-pressed',String(!enabled));
 showGrid(false);sendPreview();
}
$('#select-mode').onclick=()=>changeMode(true);
$('#browse-mode').onclick=()=>changeMode(false);
$('#source-mode').onclick=()=>{changeMode(true,true);showMessage('Cliquez sur un texte ou un bouton dans l’aperçu.');};
$('#grid-mode').onclick=()=>showGrid(!gridMode);
$('#reload-preview').onclick=()=>setPage(page);
$('#preview-retry').onclick=async()=>{
 if(state?.previewUrl){setPage(page);return;}
 setPreviewStatus('Ouverture du site local…');
 try{await api('/api/preview/retry',{});state={...state,previewError:null};}
 catch(error){setPreviewStatus(error.message,true);}
};
$('#log-toggle').onclick=()=>{showActivity($('#activity').hidden);$('#options-menu').open=false;};
$('#close-activity').onclick=()=>showActivity(false);
window.addEventListener('message',event=>{
 if(event.source!==$('#preview').contentWindow||event.origin!==previewOrigin||!event.data||typeof event.data!=='object')return;
 if(event.data.type==='resonant-editor:ready'){
  previewReady=true;clearTimeout(previewDeadline);setPreviewStatus('');sendPreview();
 }
 if(event.data.type==='resonant-editor:activity')previewBusy=event.data.busy===true;
 if(event.data.type==='resonant-editor:selected')showSection(event.data.key);
 if(sourceMode&&event.data.type==='resonant-editor:source')window.resonantOpenSource?.(event.data.metadata);
 if(event.data.type==='resonant-editor:move'&&selectMode&&!gridMode)moveLiveBlock(event.data);
 if(event.data.type==='resonant-editor:block'&&current()?.blocks.some(block=>block.id===event.data.id)){
  selectedBlock=event.data.id;
  showSection('layout');
 }
});
window.resonantEditorHasUnsavedChanges=()=>dirty||window.resonantSourceDirty?.()===true;
window.addEventListener('beforeunload',event=>{
 if(window.resonantEditorHasUnsavedChanges()||busy()){event.preventDefault();event.returnValue='';}
});
window.addEventListener('keydown',event=>{
 if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='s'&&!$('#file-console').open){
  event.preventDefault();if(!busy())$('#save').click();
 }
});
document.addEventListener('click',event=>{
 for(const menu of all('details.toolbar-menu[open]'))if(!menu.contains(event.target))menu.open=false;
});
document.addEventListener('keydown',event=>{
 if(event.key==='Escape')for(const menu of all('details.toolbar-menu[open]'))menu.open=false;
});
new ResizeObserver(resizePreview).observe($('.preview-stage'));resizePreview();
window.addEventListener('DOMContentLoaded',poll);
