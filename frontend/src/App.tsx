import {Fragment,type ReactNode} from 'react';
import type {LayoutPage,BlockKind} from './siteLayout';
import {LayoutGrid} from './components/LayoutGrid';
import {HardwarePlan} from './components/HardwarePlan';
import {acousticEnabled,acousticHint,acousticTrialCount,clearAcousticTrials,contribution,recordAcousticTrial,sendContribution,setAcousticEnabled,type CollectiveHistory} from './acousticLearning';
import {COMPUTE_VERSION} from './computeVersion';
import {visualEditorOrigin} from './siteSettings';
import type {AudioOrigin} from './circuitProject';
import {computeLocally,disposeCompute} from './computeEngine';
import { renderPatchClientSide } from './audioEngine';
import {useEffect,useRef,useState,useMemo} from 'react';
import {Activity,Upload,Download,AudioWaveform,FlaskConical,Network,Plus,Search,ChevronRight,RotateCcw,Settings2,X,Check,LoaderCircle,FileAudio,Save,Scissors,Cpu} from 'lucide-react';
import type {Patch,Catalog,AudioData,Analysis,Generation,RenderResult,Candidate,Weights,Job,Bode,CompactResult} from './types';
import {api,download,exportBlob,resetSession,request as apiRequest} from './api';
import {initialPatch,appendModule} from './defaults';
import {Graph} from './components/Graph';
import {Inspector} from './components/Inspector';
import {SignalPanel} from './components/SignalPanel';
import {AnalysisPanel} from './components/AnalysisPanel';
import {Player} from './components/Player';
import {Keyboard} from './components/Keyboard';
import {useComputeJob,type JobKind} from './hooks/useComputeJob';
import {Account} from './components/Account';
import {AudioInventory} from './components/AudioInventory';
import {AlgorithmHelp} from './components/AlgorithmHelp';
import {ExportLogin,type LabUser} from './components/ExportLogin';
import {Plot,colors,ExportPermission} from './components/Plot';
import {exportReport} from './report';
import {buildTeensySketch} from './firmware/teensySketch';
import {APP_VERSION} from './version';

export function App({layoutPage,extraBlocks,onNavigatePage,guideTarget,active=true,accountUser,learningOwner,resumeJob,onCreateCircuit,onAccountChange}:{layoutPage?:LayoutPage;extraBlocks?:Partial<Record<BlockKind,ReactNode>>;onNavigatePage?:(id:string)=>void;guideTarget?:string;active?:boolean;accountUser?:LabUser|null;learningOwner?:number;resumeJob?:import('./hooks/useComputeJob').ComputeJob|null;onCreateCircuit?:(patch:Patch,origin?:AudioOrigin)=>void;onAccountChange?:(user:LabUser)=>void}){
 useEffect(()=>{if(guideTarget==='graph')setTab('graph')},[guideTarget]);
 const [audioPanel,setAudioPanel]=useState<'library'|'inspector'|null>(null);
 const libraryToggle=useRef<HTMLButtonElement>(null),inspectorToggle=useRef<HTMLButtonElement>(null);
 function closeAudioPanel(panel:'library'|'inspector'){setAudioPanel(null);(panel==='library'?libraryToggle:inspectorToggle).current?.focus()}
 const [exportFile,setExportFile]=useState<{url:string;name:string}|null>(null);
 async function saveDownload(data:Blob|string,name:string,type?:string){setExportFile(await download(data,name,type))}

 const [catalog,setCatalog]=useState<Catalog>({}),[patch,setPatch]=useState<Patch>(initialPatch),[audio,setAudio]=useState<AudioData|null>(null),[analysis,setAnalysis]=useState<Analysis|null>(null),[candidates,setCandidates]=useState<Candidate[]>([]),[result,setResult]=useState<RenderResult|null>(null),[selected,setSelected]=useState('filter'),[tab,setTab]=useState('graph'),[busy,setBusy]=useState(''),[rendering,setRendering]=useState(false),[error,setError]=useState(''),[renderError,setRenderError]=useState(''),[notice,setNotice]=useState(''),[search,setSearch]=useState(''),[start,setStart]=useState(0),[duration,setDuration]=useState(3),[maxPartials,setMaxPartials]=useState(24),[penalty,setPenalty]=useState(.0001),[weights,setWeights]=useState<Weights>({time:.1,spectral:.25,spectrogram:.5,envelope:.15,attack:.25}),[showSettings,setShowSettings]=useState(false),[showExports,setShowExports]=useState(false),[detailed,setDetailed]=useState(true),[includeImpact,setIncludeImpact]=useState(true),[refineModes,setRefineModes]=useState(true),[method,setMethod]=useState('compare'),[iterations,setIterations]=useState(15),[parameterIds,setParameterIds]=useState<string[]>([]),[job,setJob]=useState<Job|null>(null),[globalBode,setGlobalBode]=useState<Bode|null>(null),[globalSource,setGlobalSource]=useState(''),[snapshots,setSnapshots]=useState<{name:string;patch:Patch;error:number|null}[]>([]),[revision,setRevision]=useState(0);
 const [protectTexture,setProtectTexture]=useState(true);
 const [focusIds,setFocusIds]=useState<string[]>([]),[compensate,setCompensate]=useState(true);
 const [modelAudioUrl, setModelAudioUrl] = useState<string|null>(null);
 const [modelBlob, setModelBlob] = useState<Blob|null>(null);
 const [compact,setCompact]=useState<CompactResult|null>(null),[tolerance,setTolerance]=useState(20),[testShaping,setTestShaping]=useState(true),[testNoise,setTestNoise]=useState(true);
 const uploadRef=useRef<HTMLInputElement>(null),patchRef=useRef<HTMLInputElement>(null);
 const [user,setUser]=useState<LabUser|null>(null);
 const [exportLogin,setExportLogin]=useState(false);
 const [learningEnabled,setLearningEnabled]=useState(false),[trialCount,setTrialCount]=useState(0);
 const sharing=!!user&&learningOwner===user.id;
 const [community,setCommunity]=useState<CollectiveHistory>({});
 const [remoteLearning,setRemoteLearning]=useState(false);
 const contributionControl=useRef<AbortController|null>(null);
 useEffect(()=>{
  if(!sharing)return;
  const controller=new AbortController();
  contributionControl.current=controller;
  return()=>{controller.abort();contributionControl.current=null;};
 },[sharing,user?.id]);

 useEffect(()=>{
  setLearningEnabled(user?acousticEnabled(user.id):false);
  setTrialCount(user?acousticTrialCount(user.id):0);
 },[user?.id]);
 function changeLearning(enabled:boolean){
  if(!user)return;
  try{setAcousticEnabled(user.id,enabled);setLearningEnabled(enabled);}
  catch{setError('La mémoire locale est indisponible dans ce navigateur.');}
 }
 function resetLearning(){
  if(!user)return;
  try{clearAcousticTrials(user.id);setTrialCount(0);}
  catch{setError('La mémoire locale est indisponible dans ce navigateur.');}
 }
 function accountConnected(next:LabUser){resetSession();try{if(user){const oldKey=`resonant-job:${user.id}`,newKey=`resonant-job:${next.id}`,pending=localStorage.getItem(oldKey);if(pending&&!localStorage.getItem(newKey))localStorage.setItem(newKey,pending);if(oldKey!==newKey)localStorage.removeItem(oldKey)}if(user&&localStorage.getItem(`resonant-guide-v2:${user.id}`)==='seen')localStorage.setItem(`resonant-guide-v2:${next.id}`,'seen')}catch{}setUser(next);onAccountChange?.(next);setExportLogin(false);setShowExports(true)}
 function openExports(){if(!user||user.guest){setExportLogin(true);return}setShowExports(v=>!v)}
 useEffect(()=>{if(accountUser===undefined)api<LabUser>('/me').then(setUser).catch(()=>{})},[accountUser]);
 const [localReady,setLocalReady]=useState(false),[localBusy,setLocalBusy]=useState(false),[localMessage,setLocalMessage]=useState('');
 const localControl=useRef<AbortController|null>(null);
 useEffect(()=>{
  setCommunity({});setRemoteLearning(false);
  if(!user)return;
  const controller=new AbortController();
  let fetching=false;
  const refreshLearning=async()=>{
   if(fetching||document.hidden)return;
   fetching=true;
   try{
    const value=await api<{history:CollectiveHistory;source?:'production'}>('/acoustic-learning',undefined,controller.signal);
    if(!controller.signal.aborted){
     const useRemote=value.source==='production';
     setRemoteLearning(useRemote&&Object.keys(value.history).length>0);
     setCommunity(useRemote||sharing||learningEnabled?value.history:{});
    }
   }catch{/* Continue with the last available observations. */}
   finally{fetching=false;}
  };
  void refreshLearning();
  const timer=setInterval(refreshLearning,300_000);
  document.addEventListener('visibilitychange',refreshLearning);
  return()=>{
   controller.abort();clearInterval(timer);
   document.removeEventListener('visibilitychange',refreshLearning);
  };
 },[learningEnabled,sharing,user?.id]);
 useEffect(()=>{let current=true;setLocalReady(false);if(user)api<{available:boolean;algorithm_version?:string}>('/compute/config').then(v=>{if(current){setLocalReady(v.available&&v.algorithm_version===COMPUTE_VERSION);}}).catch(()=>{});return()=>{current=false}},[user?.id]);
 useEffect(()=>()=>{localControl.current?.abort();disposeCompute()},[user?.id]);
 const compute=useComputeJob(user?.id,consumeResult,true);
 useEffect(()=>{if(accountUser!==undefined)setUser(accountUser)},[accountUser]);
 useEffect(()=>{if(resumeJob)compute.resume(resumeJob)},[resumeJob]);
 useEffect(()=>{if(!active){localControl.current?.abort();if(compute.busy)void compute.cancel().catch(()=>{});document.querySelectorAll('audio').forEach(a=>a.pause())}},[active]);
 async function submitCompute(kind:JobKind,parameters:unknown){
  if(!localReady){setError('Le moteur local Python/SciPy n’est pas disponible. Aucun calcul serveur n’est lancé.');return}
  if(localControl.current||compute.busy||!user)return;
  const controller=new AbortController();localControl.current=controller;setLocalBusy(true);setError('');setLocalMessage('Chargement de la référence en double précision…');
  try{
   const hint=kind==='generate'&&(sharing||remoteLearning||acousticEnabled(user.id))?acousticHint(user.id,community,sharing):undefined;
   let ticket='';
   const shareSignal=contributionControl.current?.signal;
   const receiveTicket=hint&&sharing?(value:string)=>{ticket=value;}:undefined;
   const value=await computeLocally(kind,parameters,controller.signal,update=>{
    if(update.phase==='initializing')setLocalMessage('Initialisation Python / SciPy sur cet appareil…');
    if(update.phase==='computing')setLocalMessage('Calcul en cours sur cet appareil ; aucun calcul serveur en file.');
    if(update.phase==='progress'&&kind==='optimize')setJob({status:'running',progress:update.progress??{}});
   },hint,receiveTicket);
   if(!controller.signal.aborted){
    if(hint){
     const trial=(value as Generation).learning;
     recordAcousticTrial(user.id,trial);
     const report=ticket?contribution(ticket,trial):null;
     if(report&&shareSignal)void sendContribution(report,shareSignal);
     setTrialCount(acousticTrialCount(user.id));
    }
    await consumeResult(kind,value,controller.signal);
    if(!controller.signal.aborted)setLocalMessage('Calcul local terminé. Le modèle est chargé.');
   }
  }catch(e){if(kind==='optimize')setJob(j=>j?{...j,status:controller.signal.aborted?'cancelled':'failed'}:null);if(controller.signal.aborted)setLocalMessage('Calcul local annulé.');else{setError(e instanceof Error?e.message:String(e));setLocalMessage('Aucun repli automatique. Vérifiez le runtime local puis relancez.')}}
  finally{if(localControl.current===controller){localControl.current=null;setLocalBusy(false)}}
 }
 const [draftLoaded,setDraftLoaded]=useState(false);
 useEffect(()=>{setDraftLoaded(false);if(!user)return;let current=true;try{const raw=localStorage.getItem('resonant-audio-draft:'+user.id);if(raw){const draft=JSON.parse(raw);void api<Patch>('/patch/validate',draft.patch).then(p=>{if(current){setPatch(p);setFocusIds(Array.isArray(draft.focusIds)?draft.focusIds.filter((id:unknown)=>typeof id==='string').slice(0,128):[]);setAudio(draft.audio??null);setAnalysis(draft.analysis??null);setStart(draft.start??0);setDuration(p.duration);setDraftLoaded(true)}}).catch(()=>{if(current){setNotice('Brouillon audio incompatible : importez un modèle.');setDraftLoaded(true)}})}else setDraftLoaded(true)}catch{setDraftLoaded(true)}return()=>{current=false}},[user?.id]);
 useEffect(()=>{if(!user||!draftLoaded)return;const timer=setTimeout(()=>{try{localStorage.setItem('resonant-audio-draft:'+user.id,JSON.stringify({patch,audio,analysis,start,focusIds}))}catch{setNotice('Le brouillon audio ne peut pas être enregistré localement. Exportez le modèle pour le conserver.')}},500);return()=>clearTimeout(timer)},[user?.id,draftLoaded,patch,audio,analysis,start,focusIds]);
 useEffect(()=>{const warn=(e:BeforeUnloadEvent)=>{if(localBusy){e.preventDefault();e.returnValue=''}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn)},[localBusy]);
 const jobId=compute.busy&&compute.job?.kind==='optimize'?compute.job.id:'';
 const locked=!!busy||compute.busy||localBusy||!user;
 useEffect(()=>{
  if(import.meta.env.DEV&&visualEditorOrigin&&window.parent!==window&&new URLSearchParams(location.search).get('editor')==='1')
   window.parent.postMessage({type:'resonant-editor:activity',busy:!!busy||localBusy||compute.busy},visualEditorOrigin);
 },[busy,localBusy,compute.busy]);
 useEffect(()=>{if(compute.job?.kind==='optimize')setJob({...compute.job,progress:compute.job.progress} as Job)},[compute.job]);
 const signature=useMemo(()=>JSON.stringify({nodes:patch.nodes.map(({id,type,parameters})=>({id,type,parameters})),edges:patch.edges,fs:patch.sample_rate,duration:patch.duration}),[patch]);
 const referenceCache=useRef<{key:string;samples:Float64Array}|null>(null);
 const selectedBlock=patch.nodes.find(n=>n.id===selected);
 useEffect(()=>{api<Catalog>('/blocks').then(setCatalog).catch(e=>setError('Serveur indisponible : '+e.message))},[]);
 useEffect(()=>{
  if(!active||!Object.keys(catalog).length||locked)return;
  const controller=new AbortController();setRenderError('');setRendering(true);setResult(null);setModelBlob(null);
  const timer=setTimeout(async()=>{
   try{
    let reference:Float64Array|undefined;
    if(audio){
     const key=`${audio.id}:${start}:${patch.duration}:${patch.sample_rate}`;
     try{
      if(referenceCache.current?.key!==key){
       const response=await apiRequest(`/audio/${audio.id}/segment?start=${start}&duration=${patch.duration}`,undefined,controller.signal);
       const context=new OfflineAudioContext(1,1,patch.sample_rate),decoded=await context.decodeAudioData(await response.arrayBuffer());
       if(controller.signal.aborted)return;
       referenceCache.current={key,samples:Float64Array.from(decoded.getChannelData(0))};
      }
      reference=referenceCache.current.samples;
     }catch(e){if(controller.signal.aborted)return;setNotice('Référence indisponible : réimportez le WAV pour comparer. Le modèle reste jouable.')}
    }
    let audioDelivered=false;
    const {blob,result}=await renderPatchClientSide(patch,catalog,controller.signal,reference,blob=>{
     if(controller.signal.aborted)return;audioDelivered=true;setModelBlob(blob);setModelAudioUrl(URL.createObjectURL(blob));
    });
    if(controller.signal.aborted)return;
    if(!audioDelivered){setModelBlob(blob);setModelAudioUrl(URL.createObjectURL(blob))}setResult(result);
   }catch(e){if(!controller.signal.aborted)setRenderError(e instanceof Error?e.message:String(e))}
   finally{if(!controller.signal.aborted)setRendering(false)}
  },450);
  return()=>{controller.abort();clearTimeout(timer)};
 },[active,signature,catalog,locked,revision,audio?.id,start]);
 useEffect(()=>()=>{if(modelAudioUrl)URL.revokeObjectURL(modelAudioUrl)},[modelAudioUrl]);
 useEffect(()=>{setGlobalBode(null)},[signature]);
 async function task(label:string,fn:()=>Promise<void>){setBusy(label);setError('');try{await fn()}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy('')}}
 function acceptAudio(a:AudioData){setCompact(null);setAudio(a);setAnalysis(null);setCandidates([]);setResult(null);setStart(0);const d=Math.min(3,a.metadata.duration);setDuration(d);setPatch(p=>({...p,duration:d}));setNotice('WAV chargé. Prêt à analyser.');setTab('analysis');setJob(null)}
 async function upload(file:File){await task('Import du WAV',async()=>{const form=new FormData();form.append('file',file);acceptAudio(await api<AudioData>('/audio',form))})}
 const request={audio_id:audio?.id,start,duration,max_partials:maxPartials,weights,complexity_penalty:penalty,include_impact:includeImpact,refine_modes:refineModes,detailed};
 async function analyze(){if(!localReady){setError('Le runtime local est indisponible.');return}if(localControl.current||locked)return;const c=new AbortController();localControl.current=c;setLocalBusy(true);setError('');setLocalMessage('Préparation de l’analyse locale…');try{const result=await computeLocally('analyze',request,c.signal,u=>setLocalMessage(u.phase==='initializing'?'Initialisation Python / SciPy sur cet appareil…':'Analyse sur cet appareil…'));if(!c.signal.aborted){setAnalysis(result as Analysis);setTab('analysis');setNotice('Analyse locale terminée.');setLocalMessage('Analyse locale terminée.')}}catch(e){if(c.signal.aborted)setLocalMessage('Analyse locale annulée.');else setError(e instanceof Error?e.message:String(e))}finally{if(localControl.current===c){localControl.current=null;setLocalBusy(false)}}}
 async function consumeResult(kind:JobKind,value:unknown,signal?:AbortSignal){
  if(kind==='generate'){
   const g=value as Generation;setFocusIds([]);setDuration(g.patch.duration);setCompact(null);setAnalysis(g.analysis);setCandidates(g.candidates);setPatch(await api<Patch>('/patch/expand',g.patch,signal));setParameterIds([]);setSelected(g.patch.nodes[0]?.id??'');setTab('graph');setNotice(g.learning?.accepted?'Un affinage a amélioré le modèle.':'Modèle prêt. Vous pouvez l’écouter.');
  }else if(kind==='compact'){
   const c=value as CompactResult;setDuration(c.patch.duration);setCompact(c);setCandidates(c.candidates);setPatch(await api<Patch>('/patch/expand',c.patch,signal));setParameterIds([]);setSelected(c.patch.nodes[0]?.id??'');setTab('graph');setNotice(`Simplification : ${c.original_blocks} → ${c.final_blocks} modules. Comparez les sons à l’écoute.`);
  }else{
   const result=value as import('./types').Optimization;setCompact(null);setCandidates([]);setDuration(result.patch.duration);setPatch(result.patch);setJob(j=>({...j,progress:j?.progress??{},status:'succeeded',result}));setNotice(`Optimisation : ${result.initial.toFixed(4)} → ${result.final.toFixed(4)}. ${result.message}`);
  }
 }
 function generate(){void submitCompute('generate',request)}
 function simplify(){
  const preserve_chain=focusIds.length>0||!patch.nodes.some(n=>n.type==='modal'||n.type==='envelope');
  void submitCompute('compact',{patch,audio_id:audio?.id,start,weights,tolerance:tolerance/100,
   test_shaping:testShaping,test_noise:testNoise,protect_texture:protectTexture,preserve_chain});
 }
 async function restorePrecision(){if(!compact)return;await task('Restauration du modèle',async()=>setPatch(await api<Patch>('/patch/expand',compact.original)));setSelected(compact.original.nodes[0]?.id??'');setParameterIds([]);setNotice('Version précise restaurée, avec ses paramètres d’origine.');setTab('graph')}
 function optimize(){setJob(null);setTab('optimization');void submitCompute('optimize',{patch,audio_id:audio?.id,start,weights,method,max_iterations:iterations,parameter_ids:parameterIds,focus_ids:focusIds,compensate})}
 function edit(p:Patch,manual=true){
  if(manual){
   const previous=new Map(patch.nodes.map(node=>[node.id,node]));
   const oldEdges=new Set(patch.edges.map(edge=>edge.source+'\0'+edge.target));
   const newEdges=new Set(p.edges.map(edge=>edge.source+'\0'+edge.target));
   const changed=new Set(p.nodes.filter(node=>{
    const before=previous.get(node.id);
    return !before||before.type!==node.type||JSON.stringify(before.parameters)!==JSON.stringify(node.parameters);
   }).map(node=>node.id));
   const wiringChanged=oldEdges.size!==newEdges.size||[...oldEdges].some(edge=>!newEdges.has(edge));
   if(wiringChanged||p.nodes.length!==patch.nodes.length)setParameterIds([]);
   for(const edge of [...oldEdges,...newEdges]){
    if(oldEdges.has(edge)!==newEdges.has(edge))edge.split('\0').forEach(id=>changed.add(id));
   }
   if(changed.size||p.nodes.length!==patch.nodes.length||p.sample_rate!==patch.sample_rate||p.duration!==patch.duration){
    setFocusIds(ids=>p.nodes.map(node=>node.id).filter(id=>changed.has(id)||ids.includes(id)));
    setCompact(null);setCandidates([]);setJob(null);
   }
  }
  setPatch(p);setNotice('');
  setParameterIds(ids=>ids.filter(id=>p.nodes.some(n=>id.startsWith(n.id+':'))));
 }
 function addBlock(type:string){const added=appendModule(patch,type,catalog,{x:100+(patch.nodes.length%4)*230,y:300+Math.floor(patch.nodes.length/4)*110});edit(added.patch);setSelected(added.id);setTab('graph')}
 async function chooseCandidate(c:Candidate){await task('Dépliage des modules',async()=>edit(await api<Patch>('/patch/expand',c.patch),false));setSelected(c.patch.nodes[0]?.id??'');setTab('graph')}
 async function importPatch(file:File){await task('Validation du modèle',async()=>{if(file.size>2_000_000)throw Error('JSON limité à 2 Mo.');const p=await api<Patch>('/patch/validate',JSON.parse(await file.text()));setFocusIds(p.nodes.map(node=>node.id));setPatch(await api<Patch>('/patch/expand',p));setSelected(p.nodes[0]?.id??'');setTab('graph');setNotice('Modèle importé et validé.');setCompact(null);setCandidates([]);setParameterIds([])})}
 async function doExport(kind:string){if(!user||user.guest){setExportLogin(true);return}setShowExports(false);await task('Export',async()=>{if(kind==='json'){const normalized=await api<Patch>('/patch/validate',patch);await saveDownload(JSON.stringify(normalized,null,2),'resonant.monpatch')}if(kind==='wav'){if(!modelBlob)throw Error('Générez un signal valide avant l’export.');await saveDownload(modelBlob,'resonant.wav')}if(kind==='svg'||kind==='csv')await saveDownload(await exportBlob('/export/'+kind,patch),'resonant.'+kind);if(kind==='arduino'||kind==='tinkered'){const build=buildTeensySketch(patch,analysis);await saveDownload(kind==='arduino'?build.code:build.prompt,kind==='arduino'?'resonant_teensy.ino':'resonant_tinkered_brief.txt','text/plain;charset=utf-8')}if(kind==='png'){const blob=await exportBlob('/export/svg',patch);const url=URL.createObjectURL(blob);try{const image=new Image();image.src=url;await image.decode();const canvas=document.createElement('canvas');canvas.width=image.width*2;canvas.height=image.height*2;canvas.getContext('2d')!.drawImage(image,0,0,canvas.width,canvas.height);const png=await new Promise<Blob|null>(resolve=>canvas.toBlob(resolve));if(png)await saveDownload(png,'resonant-graphe.png')}finally{URL.revokeObjectURL(url)}}if(kind==='report')setExportFile(await exportReport(patch,audio,analysis,result,weights,start))})}
 function updateSelection(s:number,d:number){setCompact(null);setStart(s);setDuration(d);setAnalysis(null);setCandidates([]);setPatch(p=>({...p,duration:d}))}
 const categories=Array.from(new Set(Object.values(catalog).map(d=>d.category)));
 const displayStatus=busy|| (jobId?'Optimisation en cours':rendering?'Calcul du signal':renderError?'Graphe à compléter':result?'Moteur prêt':'Connexion au moteur');
 const referenceBlock=<><section className="source-panel" data-guide="reference"><div className="source-icon"><FileAudio size={23}/></div><div className="source-details"><div className="eyebrow">SIGNAL DE RÉFÉRENCE</div><b>{audio?audio.metadata.name:'Importez un son à reproduire'}</b><small>{audio?`${audio.metadata.duration.toFixed(2)} s · ${audio.metadata.sample_rate.toLocaleString('fr-FR')} Hz · ${audio.metadata.channels===1?'mono':'stéréo → analyse mono'}`:'Fichier WAV'}</small></div>{!audio?<button className="text-button" disabled={locked} onClick={()=>{void task('Chargement de la démonstration',async()=>acceptAudio(await api<AudioData>('/demo',{})))}}>Essayer une note modale <ChevronRight size={14}/></button>:<div className="selection"><label>Début <input aria-label="Début de sélection" disabled={locked} type="number" min="0" max={Math.max(0,audio.metadata.duration-.05)} step=".01" value={start} onChange={e=>{if(Number.isFinite(e.target.valueAsNumber))updateSelection(Math.max(0,Math.min(audio.metadata.duration-.05,e.target.valueAsNumber)),Math.min(duration,audio.metadata.duration-Math.max(0,Math.min(audio.metadata.duration-.05,e.target.valueAsNumber))))}}/> s</label><label>Durée <input aria-label="Durée de sélection" disabled={locked} type="number" min=".05" max={Math.min(12,audio.metadata.duration-start)} step=".01" value={duration} onChange={e=>{if(Number.isFinite(e.target.valueAsNumber))updateSelection(start,Math.max(.05,Math.min(12,audio.metadata.duration-start,e.target.valueAsNumber)))}}/> s</label></div>}</section>
 <div className="compute-location"><span>Calcul sur cet appareil · {localReady?'Prêt':'runtime local indisponible'}</span>{localMessage&&<span role="status">{localMessage}</span>}{localBusy&&<button onClick={()=>localControl.current?.abort()}>Annuler le calcul</button>}</div><div className="action-bar"><button ref={libraryToggle} aria-controls="audio-library" aria-expanded={audioPanel==='library'} onClick={()=>setAudioPanel(p=>p==='library'?null:'library')}>Blocs</button><button ref={inspectorToggle} aria-controls="audio-inspector" aria-expanded={audioPanel==='inspector'} onClick={()=>setAudioPanel(p=>p==='inspector'?null:'inspector')}>Propriétés</button><div className="workflow-buttons"><button disabled={!audio||locked} onClick={()=>void analyze()}><Search size={15}/><span>1. Analyser</span></button><button data-guide="generate" className="primary" disabled={!audio||locked} onClick={()=>void generate()}><Network size={15}/><span>2. Générer le modèle</span></button><button disabled={!audio||locked||!!renderError||rendering} onClick={()=>void optimize()}><FlaskConical size={15}/><span>3. Optimiser</span></button><button disabled={!audio||locked||!!renderError||rendering} onClick={()=>void simplify()}><Scissors size={15}/><span>4. Simplifier</span></button></div><button className={showSettings?'active':''} aria-label="Réglages de l’analyse" onClick={()=>setShowSettings(!showSettings)}><Settings2 size={17}/></button></div>
 {compute.message&&<div className="job-notice" role="status">{compute.busy&&<LoaderCircle className="spin" size={16}/>}<span>{compute.message}</span>{compute.trackingError&&compute.busy&&<><a href="/login">Connexion</a><button onClick={compute.retry}>Reprendre le suivi</button></>}{compute.busy&&compute.job&&['queued','running'].includes(compute.job.status)&&<button onClick={()=>void compute.cancel().catch(e=>setError(e.message))}>Annuler le calcul</button>}</div>}
 {busy&&<div className="task-progress" role="status"><LoaderCircle className="spin" size={16}/><span>{busy}…{busy==='Identification des modèles'?' Ajustement des modes et de l’attaque en cours.':busy==='Recherche du modèle compact'&&testShaping?' Comparaison de sources, saturations et chaînes de filtres ; durée dépendante de cet appareil.':''}</span></div>}
 </>;
 const settingsBlock=<> {showSettings&&<div className="settings"><label>Partiels max.<input type="number" min="1" max="24" disabled={locked} value={maxPartials} onChange={e=>setMaxPartials(Math.max(1,Math.min(24,+e.target.value)))}/></label><label>Parcimonie λ<input type="number" min="0" max="1" step=".0001" disabled={locked} value={penalty} onChange={e=>setPenalty(Math.max(0,Math.min(1,+e.target.value)))}/></label><label>Échantillonnage<select value={patch.sample_rate} disabled={locked} onChange={e=>edit({...patch,sample_rate:+e.target.value})}>{[44100,48000,96000].map(v=><option key={v} value={v}>{v} Hz</option>)}</select></label>{!audio&&<label>Durée (s)<input type="number" min=".05" max="60" step=".1" value={patch.duration} disabled={locked} onChange={e=>edit({...patch,duration:+e.target.value})}/></label>}{Object.entries(weights).map(([k,v])=><label key={k}>Poids {({time:'temps',spectral:'spectre',spectrogram:'STFT',envelope:'enveloppe',attack:'attaque'} as Record<string,string>)[k]}<input type="number" min="0" max="100" step=".05" value={v} disabled={locked} onChange={e=>{setCompact(null);setWeights({...weights,[k]:Math.max(0,Math.min(100,+e.target.value))});setCandidates([])}}/></label>)}<label className="checkbox-setting"><input type="checkbox" checked={refineModes} disabled={locked} onChange={e=>setRefineModes(e.target.checked)}/> Affiner modes et battements</label><label className="checkbox-setting"><input type="checkbox" checked={detailed} disabled={locked||!refineModes} onChange={e=>setDetailed(e.target.checked)}/> Recherche détaillée (plus lente)</label><label className="checkbox-setting"><input type="checkbox" checked={includeImpact} disabled={locked} onChange={e=>setIncludeImpact(e.target.checked)}/> Identifier un bruit d’impact</label><label>Hausse d’erreur max. (%)<input aria-label="Hausse d’erreur maximale" type="number" min="0" max="100" step="5" disabled={locked} value={tolerance} onChange={e=>{if(Number.isFinite(e.target.valueAsNumber))setTolerance(Math.max(0,Math.min(100,e.target.valueAsNumber)))}}/></label><label className="checkbox-setting"><input type="checkbox" checked={testShaping} disabled={locked} onChange={e=>setTestShaping(e.target.checked)}/> Tester sinus + saturations + filtres + enveloppes (plus lent)</label><label className="checkbox-setting"><input type="checkbox" checked={testNoise} disabled={locked} onChange={e=>setTestNoise(e.target.checked)}/> Tester le bruit blanc filtré pour l’attaque et les aigus diffus</label><label className="checkbox-setting"><input type="checkbox" checked={protectTexture} disabled={locked} onChange={e=>setProtectTexture(e.target.checked)}/> Protéger l’attaque et chaque bande de fréquences</label><label>Algorithme<select value={method} disabled={locked} onChange={e=>setMethod(e.target.value)}><option value="compare">Comparer les trois</option><option value="Powell">JeanJacky</option><option value="L-BFGS-B">Jean Neymar</option><option value="differential_evolution">Évolution différentielle</option></select></label><AlgorithmHelp method={method}/><label className="checkbox-setting"><input type="checkbox" checked={compensate} disabled={locked||parameterIds.length>0} onChange={e=>setCompensate(e.target.checked)}/> Tester un égaliseur après saturation</label><label>Budget d’itérations<input type="number" min="1" max="60" disabled={locked} value={iterations} onChange={e=>setIterations(Math.max(1,Math.min(60,+e.target.value)))}/></label><details className="calculation-details"><summary>Mémoire d’apprentissage</summary>
 <label className="checkbox-setting"><input type="checkbox" checked={learningEnabled} disabled={locked} onChange={e=>changeLearning(e.target.checked)}/> Apprendre sur cet appareil</label>
 {trialCount>0&&<button disabled={locked} onClick={resetLearning}>Effacer les essais ({trialCount})</button>}</details>
 <details className="calculation-details"><summary>Détails du calcul</summary><p>Optimisation : {parameterIds.length?`${parameterIds.length} paramètres cochés`:'paramètres réglables sur le trajet vers la sortie, dans la limite du budget'}. Génération : la référence utilise erreur + λ × complexité ; la recherche retient ensuite le moins de blocs sans dégrader les critères mesurés. Bruit + peigne et saturations + filtres sont toujours comparés. Les options de bruit et de tolérance ci-dessus concernent la simplification. Les scores candidats sont ceux de leur génération. Simplification : choisir le moins de blocs sous la limite d’erreur, relativement à la version précise. +20 % de coût ne signifie pas 20 % de perte perceptive.</p></details></div>}
</>;
 const graphBlock=<> <div className="editor-tabs"><div className="tabs"><button className={tab==='graph'?'active':''} onClick={()=>setTab('graph')}><Network size={15}/> Schéma de synthèse</button><button className={tab==='analysis'?'active':''} onClick={()=>setTab('analysis')}><AudioWaveform size={15}/> Analyse & modèles</button><button className={tab==='optimization'?'active':''} onClick={()=>setTab('optimization')}><Activity size={15}/> Optimisation</button><button data-guide="create-circuit" disabled={locked} onClick={()=>onCreateCircuit?.(patch,audio?{audioName:audio.metadata.name,sampleRate:audio.metadata.sample_rate,start,duration:patch.duration,...(analysis?{analysis:{f0:analysis.f0,partials:analysis.partials.length,attack:analysis.attack}}:{})}:undefined)}><Cpu size={15}/> Créer un montage à partir de ce modèle</button></div></div>
 {tab==='graph'?(Object.keys(catalog).length?<Graph patch={patch} catalog={catalog} onChange={edit} onSelect={id=>{setSelected(id);if(id)setAudioPanel('inspector');else if(audioPanel==='inspector')setAudioPanel(null)}} selected={selected} disabled={locked}/>:<div className="graph-wrap"/>):tab==='analysis'?<AnalysisPanel analysis={analysis} candidates={candidates} onCandidate={chooseCandidate} disabled={locked}/>:<div className="optimization-panel"><div className="optimization-heading"><div><div className="eyebrow">AJUSTEMENT NUMÉRIQUE</div><h2>Une erreur mesurée, à chaque essai.</h2></div>{jobId&&<button onClick={()=>void compute.cancel().catch(e=>setError(e.message))}>Annuler le calcul</button>}</div><div className="optimization-stats"><span>Initiale <b>{(job?.result?.initial??job?.progress.initial)?.toFixed(5)??'—'}</b></span><span>Meilleure <b>{(job?.result?.final??job?.progress.best)?.toFixed(5)??'—'}</b></span><span>Évaluations <b>{job?.result?.evaluations??job?.progress.evaluations??0}</b></span><span>Paramètres <b>{job?.result?.parameters.length??job?.progress.parameters?.length??parameterIds.length}</b></span></div><Plot plotId="optimization" height={190} data={[{y:job?.result?.history??job?.progress.history??[],type:'scatter',mode:'lines',line:{color:colors.model,width:2}}]} layout={{xaxis:{title:{text:'Évaluations de la fonction d’erreur'},gridcolor:'#28333e'},yaxis:{title:{text:'Meilleure erreur'},gridcolor:'#28333e'}}}/><details><summary>Lire la courbe</summary><p className="muted">La courbe conserve le meilleur essai. Un budget épuisé ne signifie pas que l’algorithme a convergé. Les paramètres cochés dans l’inspecteur déterminent les variables libres.</p></details>{job?.result&&<><p>{job.result.message}</p>
 {job.result.methods?.length?<ul>{job.result.methods.map(row=><li key={row.stage+row.method}>
 {({Powell:'JeanJacky','L-BFGS-B':'Jean Neymar',differential_evolution:'Évolution différentielle'} as Record<string,string>)[row.method]} · {row.stage} · erreur {row.error.toFixed(5)} · {row.evaluations} essais · {row.tested_parameters} paramètres examinés
 </li>)}</ul>:null}
 {job.result.compensation_retained&&<p>Égaliseur de compensation retenu.</p>}</>}<div className="snapshot-toolbar"><b>Versions du modèle</b><button disabled={locked||!result} onClick={()=>setSnapshots([...snapshots,{name:`Version ${snapshots.length+1}`,patch:structuredClone(patch),error:result?.errors?.total??null}])}><Save size={14}/> Mémoriser cette version</button></div>{snapshots.map((s,i)=><button className="snapshot-row" key={i} disabled={locked} onClick={()=>{edit(structuredClone(s.patch));setTab('graph')}}><b>{s.name}</b><span>{s.patch.name}</span><span>{s.patch.nodes.length} blocs · erreur {s.error?.toFixed(4)??'sans référence'}</span></button>)}</div>}
</>;
 const keyboardBlock=<details className="audio-detail"><summary>Clavier / MIDI</summary><Keyboard patch={patch} catalog={catalog} disabled={locked||!active} onPatch={p=>{edit(p);setSelected(p.nodes[0]?.id??'')}} onError={setError}/></details>;
 const signalsBlock=<details className="audio-detail"><summary>Comparer les signaux et les analyses</summary><SignalPanel original={audio?.view} result={result} analysis={analysis}/></details>;
 const playerBlock=<div data-guide="player"><Player originalUrl={audio?`/api/audio/${audio.id}/segment?start=${start}&duration=${patch.duration}`:undefined} modelUrl={modelAudioUrl||undefined} onError={setError}/></div>;
 const knobsBlock=<div className="layout-knobs">{patch.nodes.filter(n=>n.type!=='output'&&catalog[n.type]).map(n=><details key={n.id}><summary>{n.label||catalog[n.type].label}</summary>{Object.entries(catalog[n.type].parameters).filter(([key])=>key!=='seed').map(([key,p])=>{
  const hi=['frequency','fc'].includes(key)?Math.min(p.maximum,patch.sample_rate*.499):p.maximum;
  const value=n.parameters[key]??p.default;
  return <label key={key}>{p.label}<output>{Number(value.toPrecision(4))} {p.unit}</output><input aria-label={p.label} type="range" min={p.minimum} max={hi} step="any" value={value} disabled={locked} onChange={event=>edit({...patch,nodes:patch.nodes.map(block=>block.id===n.id?{...block,parameters:{...block.parameters,[key]:event.target.valueAsNumber}}:block)})}/></label>;
 })}</details>)}</div>;
 const inventoryBlock=<AudioInventory patch={patch} catalog={catalog}/>;
 const compactBlock=<> {compact&&<section className="compact-summary" aria-label="Comparaison de simplification"><div className="compact-heading"><div><div className="eyebrow">DERNIÈRE COMPARAISON · PRÉCISION / SOBRIÉTÉ</div><h3>{compact.original_blocks} → {compact.final_blocks} blocs <small>· {compact.original_generators} → {compact.final_generators} générateurs</small></h3></div><button disabled={locked} onClick={restorePrecision}><RotateCcw size={13}/> Revenir à la version précise</button></div><p>Erreur pondérée : <b>{compact.baseline.toFixed(4)} → {compact.final.toFixed(4)}</b> · plafond {compact.limit.toFixed(4)} (+{Math.round(compact.tolerance*100)} %). {compact.reverted?'Aucune réduction retenue.':'Le candidat retenu utilise le moins de blocs parmi les essais sous ce plafond.'}</p><details><summary>Comprendre la comparaison</summary><p>Ce coût n’est pas un pourcentage de ressemblance. Comptage : chaque mode inclut un sinus et une enveloppe, soit deux blocs visibles. Ce décompte ne mesure ni les composants physiques ni leur consommation.</p></details>{compact.final_bands&&<div className="compact-bands">{Object.entries(compact.final_bands).map(([key,value])=><span key={key}>{key} : {compact.reference_bands?.[key].toFixed(3)} → {value.toFixed(3)} </span>)}<small>{compact.protect_texture?'Attaque et bandes protégées par le budget.':'Budget appliqué au coût global uniquement.'}</small></div>}<div className="compact-actions"><button disabled={locked} onClick={()=>{void task('Dépliage des modules',async()=>setPatch(await api<Patch>('/patch/expand',compact.patch)));setSelected(compact.patch.nodes[0]?.id??'');setParameterIds([]);setTab('graph')}}>Charger le modèle retenu</button><button onClick={()=>setTab('analysis')}>Comparer tous les candidats</button><button onClick={()=>setShowSettings(true)}>Régler le budget d’erreur</button></div>{compact.processing_diagnostics&&compact.processing_diagnostics.length>0&&<details className="processing-trials"><summary>Recherche globale : {compact.processing_diagnostics.length} architectures de saturation et filtrage comparées</summary><p>Sources réajustées avec saturation asymétrique ×4, passe-bas, passe-haut et égaliseur ; filtres avant/après saturation, branche parallèle, ou création d’harmoniques avant une enveloppe commune. Les traitements disposent de leur propre étape d’ajustement avant la recherche conjointe. Chaque coût est revérifié à la fréquence originale. Plus de filtres n’est retenu que si le compromis le justifie.</p><div className="table-scroll"><table><thead><tr><th>Architecture</th><th>Blocs</th><th>Erreur</th></tr></thead><tbody>{compact.processing_diagnostics.map((d,i)=><tr key={i}><td>{d.architecture}</td><td>{d.blocks}</td><td>{d.full_rate_error.toFixed(4)}</td></tr>)}</tbody></table></div></details>}<details><summary>Bruit filtré : {compact.texture_diagnostics?.length??0} propositions améliorant le résidu</summary><p>{compact.noise_tested?"Recherche effectuée avec un passe-haut, un passe-bande ou un passe-haut + passe-bas, puis une enveloppe explicite. Le niveau est le réglage d’amplitude de la source de bruit ; aucun amplificateur n’est dissimulé.":"Recherche de bruit désactivée pour cette comparaison."} Un AOP amplifie le signal ; un bruit filtré conserve une part aléatoire et ne remplace pas automatiquement les harmoniques stables. Chaque candidat reste soumis au budget d’erreur.</p>{!!compact.texture_diagnostics?.length&&<div className="table-scroll"><table><thead><tr><th>Architecture</th><th>Blocs</th><th>Erreur</th></tr></thead><tbody>{compact.texture_diagnostics.map((d,i)=><tr key={i}><td>{d.architecture}</td><td>{d.blocks}</td><td>{d.full_rate_error.toFixed(4)}</td></tr>)}</tbody></table></div>}</details><details><summary>Utilité des blocs du modèle retenu</summary><p>Hausse du coût lorsque l’on coupe une source ou contourne un traitement, sans réajuster les autres. Une valeur négative indique une interférence défavorable. Ces mesures concernent le modèle retenu lors du calcul.</p><div className="compact-utilities">{compact.utilities.map(u=><span key={u.block_id}>{u.label} <b>{u.error_increase_without>=0?'+':''}{u.error_increase_without.toFixed(5)}</b></span>)}</div></details></section>}</>;
 const statusBlock=<div className="graph-status"><span className={renderError?'orange':''}>{renderError|| (result?.clipping?'Crête > 1 : risque d’écrêtage à l’écoute ; WAV float exporté sans normalisation.':'')}</span><button disabled={locked} onClick={()=>setRevision(v=>v+1)}>{rendering?<LoaderCircle size={13} className="spin"/>:<RotateCcw size={13}/>} Recalculer</button></div>;
 const metricsBlock=<div className="error-metrics"><span>PRÉCISION</span>{result?.errors?Object.entries(result.errors).map(([k,v])=><div key={k} className={k==='total'?'total':''}><span>{({time:'Temps',spectral:'Spectre',spectrogram:'STFT',envelope:'Enveloppe',attack:'Attaque',total:'Pondérée'} as Record<string,string>)[k]}</span><b>{v.toFixed(4)}</b></div>):<small>{audio?'Rendu local. Les coûts du modèle sont disponibles dans Analyse & modèles.':'Importez une référence pour comparer les signaux.'}</small>}</div>;
 const transferBlock=<details className="global-section"><summary><Activity size={14}/> Fonction de transfert du réseau</summary><div className="global-controls"><select aria-label="Source pour le Bode global" value={globalSource} onChange={e=>setGlobalSource(e.target.value)}><option value="">Choisir le point d’injection</option>{patch.nodes.filter(n=>catalog[n.type]?.inputs===0).map(n=><option key={n.id} value={n.id}>{n.label||n.type}</option>)}</select><button disabled={!globalSource||locked} onClick={()=>void task('Calcul du transfert global',async()=>setGlobalBode(await api<Bode>('/transfer/global',{patch,source_id:globalSource})))}>Calculer H(z) global</button></div><p>Le transfert est défini d’une source vers la sortie, autres sources à zéro. Enveloppes et non-linéarités excluent une représentation LTI globale.</p>{globalBode&&<><p>{globalBode.description}</p><Plot plotId="global" height={210} data={[{x:globalBode.frequency,y:globalBode.magnitude,type:'scatter',mode:'lines',name:'Gain dB'},{x:globalBode.frequency,y:globalBode.phase,type:'scatter',mode:'lines',name:'Phase °',yaxis:'y2'}]} layout={{showlegend:true,xaxis:{type:'log',title:{text:'Fréquence (Hz)'}},yaxis:{title:{text:'Gain (dB)'}},yaxis2:{title:{text:'Phase (°)'},overlaying:'y',side:'right'},margin:{l:60,r:60,t:20,b:40}}}/></>}</details>;
 const layoutBlocks={inventory:inventoryBlock,compact:compactBlock,status:statusBlock,metrics:metricsBlock,transfer:transferBlock,knobs:knobsBlock,reference:referenceBlock,settings:settingsBlock,graph:graphBlock,keyboard:keyboardBlock,signals:signalsBlock,player:playerBlock,hardware:<HardwarePlan patch={patch}/>,...extraBlocks};
 const nativeBlocks = [
  ['reference', referenceBlock], ['settings', settingsBlock], ['inventory', inventoryBlock],
  ['compact', compactBlock], ['graph', graphBlock], ['hardware', tab==='graph'&&<HardwarePlan patch={patch}/>],
  ['status', statusBlock], ['keyboard', keyboardBlock], ['signals', signalsBlock],
  ['metrics', metricsBlock], ['player', playerBlock], ['transfer', transferBlock],
 ] as const;
 const editablePreview=import.meta.env.DEV&&window.parent!==window&&new URLSearchParams(location.search).get('editor')==='1';
 return <ExportPermission.Provider value={!!user&&!user.guest}><div className={"app-shell "+(audioPanel?"audio-"+audioPanel+"-open":"")}>
 {exportLogin&&<ExportLogin onClose={()=>setExportLogin(false)} onConnected={accountConnected}/>}
 <header className="app-header"><a className="brand" href="#" onClick={e=>e.preventDefault()}><div className="brand-mark"><Activity size={24}/></div><div>résonant<span>LAB</span></div></a><div className="project-label"><span className="project-dot"/><input aria-label="Nom du modèle" value={patch.name} disabled={locked} onChange={e=>setPatch({...patch,name:e.target.value})}/><span className="version">v{APP_VERSION}</span></div><div className="header-actions"><Account onLogin={()=>setExportLogin(true)} onUserChange={setUser} user={user} onResume={compute.resume} busy={compute.busy}/><button disabled={locked} onClick={()=>uploadRef.current?.click()}><Upload size={15}/> Importer WAV</button><div className="export-holder"><button data-guide="export" className="export-button" disabled={locked} onClick={openExports}><Download size={15}/> Exporter</button>{showExports&&<div className="export-menu">{[['json','Modèle · JSON / .monpatch'],['wav','Audio synthétisé · WAV float'],['svg','Schéma vectoriel · SVG'],['png','Schéma image · PNG'],['csv','Paramètres · CSV'],['report','Rapport autonome · HTML / impression PDF']].map(([id,label])=><button key={id} onClick={()=>void doExport(id)}>{label}</button>)}</div>}</div></div></header>
 <input ref={uploadRef} type="file" accept=".wav,audio/wav" hidden onChange={e=>{const f=e.target.files?.[0];if(f)void upload(f);e.target.value=''}}/><input ref={patchRef} type="file" accept=".json,.monpatch" hidden onChange={e=>{const f=e.target.files?.[0];if(f)void importPatch(f);e.target.value=''}}/>
 <div className="workspace-bar"><div className="breadcrumb"><FlaskConical size={15}/><span>Atelier audio</span><ChevronRight size={13}/><b>{audio?audio.metadata.name:'Création manuelle'}</b></div><div className="engine-status"><span className={busy||rendering||jobId?'pulse':''}/>{displayStatus}<span className="divider"/>{(patch.sample_rate/1000).toFixed(1)} kHz · mono</div></div>
 {(error||notice)&&<div className={`message ${error?'error':'info'}`} role={error?'alert':'status'}>{error?<InfoIcon/>:<Check size={16}/>}<span>{error||notice}</span><button aria-label="Fermer le message" onClick={()=>{setError('');setNotice('')}}><X size={15}/></button></div>}
 {exportFile&&<div className="message info" role="status"><Download size={16}/><span>Export prêt : <a href={exportFile.url} download={exportFile.name}>Télécharger {exportFile.name}</a></span><button aria-label="Fermer l’export" onClick={()=>setExportFile(null)}><X size={15}/></button></div>}
 {user?.guest&&<div className="visitor-notice" role="status">Mode visiteur : analysez, générez et écoutez librement. Un compte est nécessaire pour exporter. Session temporaire de 24 heures. WAV visiteur : 32 Mo et 4 millions d’échantillons maximum.</div>}
 <div className="workbench"><aside className="library" id="audio-library"><div className="library-heading"><div className="panel-label">COMPOSANTS</div><span>{Object.keys(catalog).length}</span><button className="audio-panel-close" type="button" aria-label="Fermer la bibliothèque de composants" title="Fermer la bibliothèque" onClick={()=>closeAudioPanel('library')}><X size={18}/></button></div><label className="search"><Search size={14}/><input placeholder="Rechercher un bloc…" aria-label="Rechercher un composant" value={search} onChange={e=>setSearch(e.target.value)}/></label><div className="library-items">{categories.map(category=><section key={category}><h4>{category}</h4>{Object.entries(catalog).filter(([_,d])=>d.category===category&&d.label.toLowerCase().includes(search.toLowerCase())).map(([type,d])=><button className="library-block" key={type} draggable={!locked} disabled={locked} onDragStart={e=>e.dataTransfer.setData('application/resonant',type)} onClick={()=>addBlock(type)}><span className={`block-symbol ${d.inputs===0?'gen':''}`}>{d.inputs===0?'∿':type==='sum'?'Σ':type==='gain'?'×':type==='delay'?'τ':'ƒ'}</span><span>{d.label}</span><Plus size={12}/></button>)}</section>)}</div><div className="library-footer"><button disabled={locked} onClick={()=>patchRef.current?.click()}><Upload size={14}/> Ouvrir un modèle</button><button disabled={locked} onClick={()=>{setCompact(null);setFocusIds([]);setPatch(initialPatch());setAudio(null);setAnalysis(null);setCandidates([]);setSelected('filter');setParameterIds([]);setNotice('Patch manuel de départ chargé.')}}><RotateCcw size={14}/> Patch de départ</button></div></aside>
 <main className="main-workspace">{layoutPage
  ? <LayoutGrid page={layoutPage} blocks={layoutBlocks} onNavigate={onNavigatePage}/>
  : nativeBlocks.map(([kind,block])=>editablePreview
   ? <section className="editor-native-block" data-editor-kind={kind} key={kind}>{block}</section>
   : <Fragment key={kind}>{block}</Fragment>)}
 </main>
 <Inspector onClose={()=>closeAudioPanel('inspector')} block={selectedBlock} catalog={catalog} fs={patch.sample_rate} locked={locked} selectedParameters={parameterIds} onToggleParameter={id=>setParameterIds(ids=>ids.includes(id)?ids.filter(i=>i!==id):[...ids,id])} onParameter={(key,value)=>edit({...patch,nodes:patch.nodes.map(n=>n.id===selected?{...n,parameters:{...n.parameters,[key]:value}}:n)})} onDelete={()=>{edit({...patch,nodes:patch.nodes.filter(n=>n.id!==selected),edges:patch.edges.filter(e=>e.source!==selected&&e.target!==selected)});setSelected('')}} onDuplicate={()=>{if(!selectedBlock)return;const id=crypto.randomUUID();edit({...patch,nodes:[...patch.nodes,{...structuredClone(selectedBlock),id,position:{x:selectedBlock.position.x+40,y:selectedBlock.position.y+120},label:selectedBlock.label+' · copie'}]});setSelected(id)}}/>
 </div>
 </div></ExportPermission.Provider>
}
function InfoIcon(){return <span aria-hidden="true">!</span>}
