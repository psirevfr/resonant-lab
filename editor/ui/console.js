'use strict';

{
 const dialog=$('#file-console'), search=$('#file-search'), list=$('#file-list');
 const editor=$('#file-content'), saveButton=$('#file-save'), status=$('#file-status');
 let files=[], file='', revision='', savedContent='', pending=false;
 const isDirty=()=>Boolean(file&&editor.value!==savedContent);
 window.resonantSourceDirty=()=>pending&&Boolean(file)||isDirty();

 function refreshConsole(){
  saveButton.disabled=pending||!isDirty();
  editor.disabled=pending||!file;
  $('#console-close').disabled=pending;
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
 async function openFile(path){
  if(pending||!confirmDiscard())return;
  pending=true;refreshConsole();
  try{
   const result=await api('/api/files/open',{name:path});
   file=path;revision=result.revision;savedContent=result.content;
   editor.value=savedContent;$('#file-name').textContent=file;
   if(editor.value!==savedContent)savedContent=editor.value; // The textarea normalises line endings.
   setStatus('');renderFiles();
  }catch(error){setStatus(error.message,true);}
  finally{pending=false;refreshConsole();if(file===path)editor.focus();}
 }
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
 editor.oninput=refreshConsole;
 saveButton.onclick=saveFile;
 $('#console-close').onclick=()=>{if(!pending&&confirmDiscard())dialog.close();};
 dialog.addEventListener('cancel',event=>{
  event.preventDefault();
  if(!pending&&confirmDiscard())dialog.close();
 });
 dialog.addEventListener('close',()=>{
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
