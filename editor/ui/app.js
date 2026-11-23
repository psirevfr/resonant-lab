'use strict';
const $=selector=>document.querySelector(selector),all=selector=>[...document.querySelectorAll(selector)],token=$('meta[name="editor-token"]').content;
$('meta[name="editor-token"]').remove();
let draft=null,saved=null,state=null,layout=null,savedLayout=null,undo=[],redo=[],lastChange=null,section='insert',gridMode=false,previewDeadline=0,page='analyse',selectMode=true,previewOrigin='',previewReady=false,previewTimer=0,requesting=false,lastJobId='',lastStatus='',dirty=false,device='desktop';
const clone=v=>JSON.parse(JSON.stringify(v));
const canonical=v=>JSON.stringify(v,(_,item)=>item&&typeof item==='object'&&!Array.isArray(item)?Object.keys(item).sort().reduce((o,k)=>(o[k]=item[k],o),{}):item);
const same=(a,b)=>canonical(a)===canonical(b);
function showMessage(text,error=false){$('#banner').textContent=text;$('#banner').classList.toggle('error',error);$('#banner').hidden=!text;}
async function api(path,body){const response=await fetch(path,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers:{'X-Editor-Token':token,...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});let result;try{result=await response.json()}catch{throw Error('La réponse de l’éditeur est illisible.')}if(!response.ok)throw Error(result.error||result.detail||'Cette action n’a pas abouti.');return result;}
function get(obj,path){return path.split('.').reduce((o,k)=>o?.[k],obj);}
function set(obj,path,value){const keys=path.split('.'),last=keys.pop();keys.reduce((o,k)=>o[k],obj)[last]=value;}
function busy(){return requesting||['running','preparing','publishing'].includes(state?.job?.status);}
function refresh(){if(!draft)return;dirty=!same(draft,saved)||!same(layout,savedLayout);$('#save-status').textContent=busy()?'Vérification en cours…':dirty?'Modifications non enregistrées':'Enregistré sur ce Mac';$('#save').disabled=busy()||!dirty;$('#prepare').disabled=busy();$('#publish').disabled=busy();$('#undo').disabled=!undo.length||busy();$('#redo').disabled=!redo.length||busy();$('#preview-page').textContent=layout?.pages.find(p=>p.id===page)?.name||draft.labels[page]||page;$('#font-value').textContent=Math.round(draft.fontScale*100)+' %';$('#radius-value').textContent=draft.radius+' px';all('[data-setting]').forEach(input=>{input.disabled=busy();const value=get(draft,input.dataset.setting);if(document.activeElement!==input)input.value=String(value);});}
function sendPreview(){clearTimeout(previewTimer);previewTimer=setTimeout(()=>{if(!draft||!previewReady||!previewOrigin)return;const frame=$('#preview');frame.contentWindow?.postMessage({type:'resonant-editor:preview',settings:draft},previewOrigin);if(layout)frame.contentWindow?.postMessage({type:'resonant-editor:layout',layout},previewOrigin);frame.contentWindow?.postMessage({type:'resonant-editor:select-mode',enabled:selectMode},previewOrigin);},80);}
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
 previewReady=false;
 setPreviewStatus('Ouverture du site local…');
 clearTimeout(previewDeadline);
 previewDeadline=setTimeout(()=>setPreviewStatus('La page locale ne répond pas.',true),18000);
 $('#preview').src=url.href;
}
function showActivity(value){$('#activity').hidden=!value;$('#log-toggle').setAttribute('aria-expanded',String(value));}
function updateJob(job){if(!job)return;const log=Array.isArray(job.log)?job.log.join('\n'):job.log||'';if($('#activity-log').textContent!==log){$('#activity-log').textContent=log;$('#activity-log').scrollTop=$('#activity-log').scrollHeight;}if(job.id!==lastJobId||job.status!==lastStatus){if(job.status==='failed')showMessage(job.error||'La vérification a échoué. Consultez le suivi.',true);if(job.readyToPublish)showMessage('Version vérifiée. Vous pouvez maintenant la publier.');if(job.status==='succeeded'&&job.stage==='Terminé')showMessage('Version envoyée sur GitHub. Le déploiement est lancé.');lastJobId=job.id;lastStatus=job.status;}}
async function poll(){
 try{
  state=draft?{...state,...await api('/api/progress')}:await api('/api/state');
  if(!draft){
   draft=clone(state.settings);saved=clone(state.settings);
   layout=clone(state.layout);savedLayout=clone(layout);page=draft.home;
   renderLayout();
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
 }catch(e){showMessage(e.message,true);}
 setTimeout(poll,busy()?1000:2000);
}
async function save(){if(!draft)return;const result=await api('/api/save',{settings:draft,layout});saved=clone(result.settings||draft);savedLayout=clone(result.layout||layout);showMessage('Présentation enregistrée.');lastChange=null;refresh();}
all('[data-setting]').forEach(input=>input.addEventListener('input',()=>{let value=input.value;const path=input.dataset.setting;if(path==='fontScale'||path==='radius')value=Number(value);if(path.startsWith('colors.')&&!/^#[0-9a-f]{6}$/i.test(value))return;edit(path,value);}));
all('[data-section]').forEach(b=>b.addEventListener('click',()=>showSection(b.dataset.section)));
all('[data-device]').forEach(b=>b.addEventListener('click',()=>{all('[data-device]').forEach(v=>v.setAttribute('aria-pressed',String(v===b)));device=b.dataset.device;$('.preview-frame').className='preview-frame '+device;resizePreview();$('#preview-menu').open=false;showGrid(false);}));
all('[data-preset]').forEach(b=>b.addEventListener('click',()=>{const colors={original:{background:'#111719',surface:'#18201f',accent:'#b4ed79',text:'#dbe4e5'},ocean:{background:'#111a20',surface:'#172a33',accent:'#81d4e8',text:'#e0edf1'},violet:{background:'#17151e',surface:'#24202e',accent:'#c6b5ff',text:'#e9e3f3'}}[b.dataset.preset];edit('colors',colors);}));
$('#undo').onclick=()=>{if(!undo.length||busy())return;redo.push(snapshot());restore(undo.pop());lastChange=null;refresh();sendPreview();};
$('#redo').onclick=()=>{if(!redo.length||busy())return;undo.push(snapshot());restore(redo.pop());lastChange=null;refresh();sendPreview();};
$('#save').onclick=async()=>{try{requesting=true;refresh();await save();}catch(e){showMessage(e.message,true);}finally{requesting=false;refresh();}};
let publicationReview=null;
async function openReview(){
 if(!draft||busy())return;
 const dialog=$('#review-dialog'),message=$('#review-summary');
 publicationReview=null;$('#run-review').disabled=true;$('#review-details').hidden=true;
 message.textContent='Lecture des commits locaux…';dialog.showModal();
 try{
  const details=await api('/api/publication-review');
  publicationReview=details;
  message.textContent=details.paths.length
   ? details.count+' commits locaux seront vérifiés. Consultez les fichiers inclus avant de continuer.'
   : 'Les réglages, les tests et la compilation seront vérifiés.';
  const list=details.paths.map(path=>{const item=document.createElement('li');item.textContent=path;return item;});
  $('#review-files').replaceChildren(...list);
  $('#review-details').hidden=!list.length;
  $('#review-details').open=details.paths.includes('.github/workflows/deploy.yml');
  $('#run-review').disabled=false;
 }catch(error){message.textContent=error.message;}
}
$('#prepare').onclick=openReview;
$('#cancel-review').onclick=()=>$('#review-dialog').close();
$('#run-review').onclick=async()=>{
 if(!publicationReview||busy())return;
 const review=publicationReview.review;
 $('#review-dialog').close();
 try{
  requesting=true;refresh();
  if(dirty)await save();
  showActivity(true);showMessage('Vérification des fichiers, des tests et de la compilation…');
  state.job=(await api('/api/prepare',{review})).job;updateJob(state.job);
 }catch(error){showMessage(error.message,true);}
 finally{requesting=false;refresh();}
};
$('#publish').onclick=()=>{
 if(!draft||busy())return;
 if(dirty||!state?.job?.readyToPublish){openReview();return;}
 $('#publish-summary').textContent='Branche '+(state.repo?.branch||'main')+' · '+(publicationReview?.count??0)+' commits vérifiés et réglages locaux.';
 $('#publish-dialog').showModal();
};
$('#cancel-publish').onclick=()=>$('#publish-dialog').close();
$('#confirm-publish').onclick=async()=>{if(requesting)return;$('#publish-dialog').close();try{requesting=true;refresh();showActivity(true);showMessage('Envoi de la version sur GitHub…');await api('/api/publish',{});state=await api('/api/state');updateJob(state.job);}catch(e){showMessage(e.message,true);}finally{requesting=false;refresh();}};
function changeMode(enabled){
 selectMode=enabled;
 $('#select-mode').setAttribute('aria-pressed',String(enabled));
 $('#browse-mode').setAttribute('aria-pressed',String(!enabled));
 showGrid(false);sendPreview();
}
$('#select-mode').onclick=()=>changeMode(true);
$('#browse-mode').onclick=()=>changeMode(false);
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
 if(event.data.type==='resonant-editor:selected')showSection(event.data.key);
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
