import {request as apiRequest} from './api';
import type {JobKind} from './hooks/useComputeJob';
export interface LocalUpdate {id:string;phase:'initializing'|'computing'|'progress'|'result'|'error';progress?:Record<string,unknown>;result?:unknown;error?:string;metrics?:Record<string,unknown>}
let worker:Worker|null=null,active:string|null=null;
export function disposeCompute(){worker?.terminate();worker=null;active=null}
if(typeof window!=='undefined')window.addEventListener('pagehide',disposeCompute);
export async function computeLocally(kind:JobKind,request:unknown,signal:AbortSignal,onUpdate:(value:LocalUpdate)=>void):Promise<unknown>{
 if(active)throw Error('Un calcul local est déjà actif.');
 const id=crypto.randomUUID();active=id;const begun=performance.now();
 try{
  const response=await apiRequest('/compute/input',{kind,request},signal);
  const sampleRate=Number(response.headers.get('X-Sample-Rate')),buffer=await response.arrayBuffer();
  if(signal.aborted)throw new DOMException('Calcul annulé','AbortError');
  if(buffer.byteLength>10_000_000||buffer.byteLength%8||![44100,48000,96000].includes(sampleRate))throw Error('Référence incompatible.');
  const input_ms=performance.now()-begun;
  worker??=new Worker(new URL('./computeWorker.ts',import.meta.url),{type:'module'});
  return await new Promise((resolve,reject)=>{
   const current=worker!;
   function clear(){signal.removeEventListener('abort',abort);current.onmessage=null;current.onerror=null;active=null}
   const abort=()=>{clear();disposeCompute();reject(new DOMException('Calcul annulé','AbortError'))};
   signal.addEventListener('abort',abort,{once:true});
   current.onerror=()=>{clear();disposeCompute();reject(Error('Le worker local a été interrompu. Relancez sur le serveur si nécessaire.'))};
   current.onmessage=event=>{
    const message=event.data as LocalUpdate;if(message.id!==id)return;
    onUpdate(message);
    if(message.phase==='error'){clear();disposeCompute();reject(Error(message.error))}
    if(message.phase==='result'){clear();console.info('resonant-compute',JSON.stringify({id,kind,location:'browser',input_ms,total_ms:performance.now()-begun,...message.metrics}));resolve(message.result)}
   };
   current.postMessage({id,kind,request,sampleRate,samples:new Float64Array(buffer)},[buffer]);
  });
 }finally{if(active===id)active=null}
}
