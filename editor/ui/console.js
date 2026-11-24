'use strict';

{
 const dialog=$('#file-console'), search=$('#file-search'), list=$('#file-list');
 const editor=$('#file-content'), saveButton=$('#file-save'), status=$('#file-status');
 let files=[], file='', revision='', savedContent='', pending=false, selection=null;
 const range=(value,length)=>Array.isArray(value)&&value.length===2&&value.every(Number.isInteger)&&
  value[0]>=0&&value[0]<value[1]&&value[1]<=length;
 const isDirty=()=>Boolean(file&&editor.value!==savedContent);
 window.resonantSourceDirty=()=>pending&&Boolean(file)||isDirty();

 function refreshConsole(){
  saveButton.disabled=pending||!isDirty();
  editor.disabled=pending||!file;
  $('#console-close').disabled=pending;
  $('#source-tools').hidden=!selection;
  $('#source-earlier').disabled=pending||!selection?.before;
  $('#source-later').disabled=pending||!selection?.after;
  $('#source-label-tools').hidden=!selection?.text;
  $('#source-rename').hidden=!selection?.text;
 }
 function setStatus(message,error=false){
  status.textContent=message;
  status.classList.toggle('error',error);
 }
 function renderFiles(){
  const query=search.value.trim().toLocaleLowerCase();
  list.replaceChildren(...files.filter(path=>path.toLocaleLowerCase().includes(query)).map(path=>{
   const item=button(path.replace(/^frontend\//,''),()=>openFile(path));
   item.title=path;
   item.setAttribute('aria-current',path===file?'true':'false');
   return item;
  }));
  if(!list.childElementCount)list.textContent='Aucun fichier trouvé';
 }
 function confirmDiscard(){
  return !isDirty()||confirm('Abandonner les modifications non enregistrées de ce fichier ?');
 }
 async function openFile(path,metadata){
  if(pending||!confirmDiscard())return;
  pending=true;refreshConsole();
  try{
   const result=await api('/api/files/open',{name:path});
   selection=null;file=path;revision=result.revision;savedContent=result.content;
   editor.value=savedContent;$('#file-name').textContent=file;
   if(editor.value!==savedContent)savedContent=editor.value; // The textarea normalises line endings.
   setStatus('');renderFiles();
   if(metadata&&metadata.revision===revision&&result.content===editor.value&&range(metadata.selected,editor.value.length)){
    const [start,end]=metadata.selected;
    selection={selected:[start,end]};
    if(range(metadata.before,editor.value.length)&&metadata.before[1]<=start)selection.before=metadata.before;
    if(range(metadata.after,editor.value.length)&&metadata.after[0]>=end)selection.after=metadata.after;
    if(range(metadata.text,editor.value.length)&&metadata.text[0]>=start&&metadata.text[1]<=end&&typeof metadata.label==='string'){
     selection.text=metadata.text;$('#source-label').value=metadata.label;
    }
    editor.setSelectionRange(...selection.selected);
   }else if(metadata)setStatus('Le fichier a changé. Actualisez l’aperçu pour retrouver le texte.');
  }catch(error){setStatus(error.message,true);}
  finally{pending=false;refreshConsole();if(file===path)editor.focus();}
 }
 window.resonantOpenSource=async raw=>{
  if(pending||dialog.open||typeof raw!=='string'||raw.length>1800)return;
  if(dirty){showMessage('Enregistrez d’abord les changements de mise en page.',true);return;}
  let metadata;
  try{metadata=JSON.parse(raw);}catch{return;}
  if(typeof metadata?.path!=='string'||!/^frontend\/src\/[\w./-]+\.[jt]sx$/.test(metadata.path))return;
  dialog.showModal();
  await openFile(metadata.path,metadata);
 };
 function moveSource(which){
  if(!selection?.[which]||pending)return;
  const [first,last]=[selection[which],selection.selected].sort((a,b)=>a[0]-b[0]);
  const content=editor.value;
  editor.setRangeText(content.slice(...last)+content.slice(first[1],last[0])+content.slice(...first),first[0],last[1],'select');
  selection=null;
  refreshConsole();
  setStatus('Bouton déplacé. Enregistrez pour actualiser l’aperçu.');
 }
 $('#source-earlier').onclick=()=>moveSource('before');
 $('#source-later').onclick=()=>moveSource('after');
 $('#source-rename').onclick=()=>{
  if(!selection?.text||pending)return;
  const value=$('#source-label').value;
  if(!value.trim())return;
  const replacements={'&':'&amp;','<':'&lt;','>':'&gt;','{':'&#123;','}':'&#125;'};
  const existing=editor.value.slice(...selection.text);
  const next=existing.match(/^\s*/)[0]+value.trim().replace(/[&<>{}]/g,character=>replacements[character])+existing.match(/\s*$/)[0];
  editor.setRangeText(next,...selection.text,'select');
  selection=null;
  refreshConsole();
  setStatus('Libellé modifié. Enregistrez pour actualiser l’aperçu.');
 };
 async function saveFile(){
  if(pending||!isDirty())return;
  pending=true;const content=editor.value;refreshConsole();
  try{
   const result=await api('/api/files/save',{name:file,content,revision});
   revision=result.revision;savedContent=content;
   if(['frontend/src/siteSettings.json','frontend/src/siteLayout.json'].includes(file)){
    state=await api('/api/state');
    synchronizePresentation(state);
   }else{
    if(state?.job)state.job.readyToPublish=false;
    // Vite applies source edits through its normal hot-reload path.
   }
   refresh();setStatus('Fichier enregistré sur ce Mac.');
  }catch(error){setStatus(error.message,true);}
  finally{pending=false;refreshConsole();editor.focus();}
 }
 $('#console-open').onclick=async()=>{
  if(dirty){showMessage('Enregistrez vos modifications visuelles avant d’ouvrir la console.',true);return;}
  $('#options-menu').open=false;
  dialog.showModal();search.focus();
  if(files.length)return;
  pending=true;refreshConsole();
  try{files=(await api('/api/files')).files;setStatus('');renderFiles();}
  catch(error){setStatus(error.message,true);}
  finally{pending=false;refreshConsole();}
 };
 search.oninput=renderFiles;
 editor.oninput=()=>{selection=null;refreshConsole();};
 saveButton.onclick=saveFile;
 $('#console-close').onclick=()=>{if(!pending&&confirmDiscard())dialog.close();};
 dialog.addEventListener('cancel',event=>{
  event.preventDefault();
  if(!pending&&confirmDiscard())dialog.close();
 });
 dialog.addEventListener('close',()=>{
  selection=null;
  editor.value=savedContent;
  refreshConsole();
 });
 dialog.addEventListener('keydown',event=>{
  if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==='s'){
   event.preventDefault();saveFile();
  }
 });
}

$('#terminal-files').onclick=()=>$('#console-open').click();
const terminalInput=$('#terminal-input'),terminalOutput=$('#terminal-output'),terminalRun=$('#terminal-run');
async function runTerminal(){
 const command=terminalInput.value.trim();
 if(!command||terminalRun.disabled)return;
 if(command==='clear'){terminalOutput.textContent='';terminalInput.value='';return;}
 terminalRun.disabled=true;terminalInput.value='';
 let output;
 try{output=(await api('/api/terminal',{command})).output;}
 catch(error){output=error.message;}
 finally{terminalRun.disabled=false;}
 terminalOutput.textContent=(terminalOutput.textContent+'\n\n$ '+command+'\n'+output).slice(-30_000);
 terminalOutput.scrollTop=terminalOutput.scrollHeight;terminalInput.focus();
}
terminalRun.onclick=runTerminal;
terminalInput.addEventListener('keydown',event=>{
 if(event.key==='Enter'){event.preventDefault();runTerminal();}
});
