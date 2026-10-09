import type {Patch,Catalog,RenderResult} from './types';
export function renderPatchClientSide(patch:Patch,catalog:Catalog,signal?:AbortSignal,reference?:Float64Array,onAudioReady?:(blob:Blob)=>void):Promise<{blob:Blob;result:RenderResult}>{
 return new Promise((resolve,reject)=>{
  const id=crypto.randomUUID(),begun=performance.now();let blob:Blob|null=null;
  const worker=new Worker(new URL('./audioWorker.ts',import.meta.url),{type:'module'});
  const dispose=()=>{worker.terminate();signal?.removeEventListener('abort',abort)};
  const abort=()=>{dispose();reject(new DOMException('Rendu interrompu','AbortError'))};
  if(signal?.aborted){abort();return}signal?.addEventListener('abort',abort,{once:true});
  worker.onerror=()=>{dispose();reject(Error('Le moteur audio local a rencontré une erreur.'))};
  worker.onmessage=event=>{
   const message=event.data;if(message.id!==id)return;
   if(message.phase==='error'){dispose();reject(Error(message.error));return}
   if(message.phase==='audio-ready'){
    blob=new Blob([message.wav],{type:'audio/wav'});onAudioReady?.(blob);
    console.info('resonant-audio',JSON.stringify({id,phase:message.phase,audio_ready_ms:performance.now()-begun,...message.metrics}));return;
   }
   if(message.phase==='analysis-ready'){
    dispose();if(!blob){reject(Error('Audio manquant.'));return}
    console.info('resonant-audio',JSON.stringify({id,phase:message.phase,total_ms:performance.now()-begun,...message.metrics}));
    resolve({blob,result:message.result});
   }
  };
  worker.postMessage({id,patch,catalog,reference});
 });
}
