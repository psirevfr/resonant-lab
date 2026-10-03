import type {Patch,Catalog,RenderResult} from './types';
export function renderPatchClientSide(patch:Patch,catalog:Catalog,signal?:AbortSignal,reference?:Float64Array):Promise<{blob:Blob;result:RenderResult}>{
 return new Promise((resolve,reject)=>{
  const worker=new Worker(new URL('./audioWorker.ts',import.meta.url),{type:'module'});
  const dispose=()=>{worker.terminate();signal?.removeEventListener('abort',abort)};
  const abort=()=>{dispose();reject(new DOMException('Rendu interrompu','AbortError'))};
  if(signal?.aborted){abort();return}signal?.addEventListener('abort',abort,{once:true});
  worker.onerror=()=>{dispose();reject(Error('Le moteur audio local a rencontré une erreur.'))};
  worker.onmessage=event=>{dispose();if(event.data.error)reject(Error(event.data.error));else resolve({blob:new Blob([event.data.wav],{type:'audio/wav'}),result:event.data.result})};
  worker.postMessage({patch,catalog,reference});
 });
}
