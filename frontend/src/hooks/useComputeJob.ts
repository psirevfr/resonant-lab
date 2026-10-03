import {useEffect,useRef,useState} from 'react';
import {api,ApiError} from '../api';
export type JobKind='generate'|'optimize'|'compact';
export interface ComputeJob{id:string;kind:JobKind;status:'queued'|'running'|'succeeded'|'failed'|'cancelled';created:number;started:number|null;finished:number|null;progress:Record<string,unknown>;error:string|null;cancel_requested:boolean}
interface Submission{id?:string;kind:JobKind;key:string;request:unknown}
export function useComputeJob(owner:number|undefined,onResult:(kind:JobKind,result:unknown)=>Promise<void>){
 const [submission,setSubmission]=useState<Submission|null>(null),[job,setJob]=useState<ComputeJob|null>(null),[message,setMessage]=useState(''),[retry,setRetry]=useState(0),[trackingError,setTrackingError]=useState(false);
 const locked=useRef(false),callback=useRef(onResult);callback.current=onResult;
 const storage=owner===undefined?null:`resonant-job:${owner}`;
 function persist(value:Submission|null){if(!storage)return;try{if(value)localStorage.setItem(storage,JSON.stringify(value));else localStorage.removeItem(storage)}catch{/* Tracking still works in memory when storage is unavailable. */}}
 useEffect(()=>{
  if(!storage)return;
  try{const saved=JSON.parse(localStorage.getItem(storage)||'null');if(saved&&['generate','optimize','compact'].includes(saved.kind)&&typeof saved.key==='string'){setSubmission(saved);locked.current=true}}catch{localStorage.removeItem(storage)}
 },[storage]);
 useEffect(()=>{
  if(!submission||!storage)return;
  let stopped=false,timer:ReturnType<typeof setTimeout>|undefined,failures=0;
  const controller=new AbortController();let current={...submission};
  async function follow(){
   try{
    setTrackingError(false);
    if(!current.id){setMessage('Enregistrement de la demande…');const created=await api<ComputeJob>('/'+current.kind,current.request,controller.signal,{'Idempotency-Key':current.key});current={...current,id:created.id};persist(current);if(stopped)return;setJob(created)}
    const status=await api<ComputeJob>('/jobs/'+current.id,undefined,controller.signal);if(stopped)return;setJob(status);failures=0;
    if(status.status==='succeeded'){
     setMessage('Calcul terminé. Chargement du modèle…');
     const result=await api<unknown>('/jobs/'+current.id+'/result',undefined,controller.signal);if(stopped)return;
     await callback.current(current.kind,result);if(stopped)return;
     persist(null);setSubmission(null);locked.current=false;setMessage('Calcul terminé. Modèle chargé.');return;
    }
    if(status.status==='failed'||status.status==='cancelled'){
     persist(null);setSubmission(null);locked.current=false;setMessage(status.error??'Calcul annulé. Vous pouvez lancer une nouvelle tentative.');return;
    }
    setMessage(status.cancel_requested?'Annulation demandée…':status.status==='queued'?'Demande en file d’attente. Le worker la prendra en charge.':'Calcul en cours sur le serveur. Vous pouvez revenir plus tard.');
    timer=setTimeout(follow,document.hidden?15000:3000);
   }catch(e){
    if(stopped||controller.signal.aborted)return;setTrackingError(true);
    if(e instanceof ApiError&&e.status===401){setMessage('Session expirée. Reconnectez-vous, puis reprenez le suivi ; le calcul peut continuer.');return}
    if(e instanceof ApiError&&[400,403,404,409,413,422,429].includes(e.status)){
     setMessage(e.message);
     if(!current.id){persist(null);setSubmission(null);locked.current=false}
     return;
    }
    setMessage('Suivi momentanément indisponible. Cela ne confirme pas un échec du calcul. Nouvelle vérification automatique…');
    timer=setTimeout(follow,Math.max(document.hidden?15000:3000,Math.min(30000,3000*2**failures++)));
   }
  }
  void follow();return()=>{stopped=true;controller.abort();if(timer)clearTimeout(timer)};
 },[submission,storage,retry]);
 function submit(kind:JobKind,request:unknown){
  if(locked.current||!storage)return;locked.current=true;
  const value={kind,request,key:crypto.randomUUID()};persist(value);setJob(null);setMessage('Envoi de la demande…');setSubmission(value);
 }
 function resume(value:ComputeJob){if(locked.current)return;locked.current=true;const next={id:value.id,kind:value.kind,key:'resume',request:{}};persist(next);setSubmission(next);setJob(value)}
 async function cancel(){if(job)await api('/jobs/'+job.id+'/cancel',{});setRetry(v=>v+1)}
 return {job,message,busy:!!submission,trackingError,submit,resume,cancel,retry:()=>setRetry(v=>v+1)};
}
