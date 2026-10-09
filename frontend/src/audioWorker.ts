import {renderGraph,signalView,encodeWav} from './audioDsp';
import type {Patch,Catalog} from './types';
self.onmessage=(event:MessageEvent<{id:string;patch:Patch;catalog:Catalog;reference?:Float64Array}>)=>{
 const {id,patch,catalog,reference}=event.data;
 try{
  let begun=performance.now();const samples=renderGraph(patch,catalog),render_ms=performance.now()-begun;
  begun=performance.now();const wav=encodeWav(samples,patch.sample_rate),encode_ms=performance.now()-begun;
  // HTML audio playback currently requires a WAV; transfer it before expensive views.
  self.postMessage({id,phase:'audio-ready',wav,metrics:{render_ms,encode_ms}},{transfer:[wav]});
  begun=performance.now();const view=signalView(samples,patch.sample_rate);
  const ref=reference&&reference.length===samples.length?reference:undefined;
  const result={id:'local',view,sample_rate:patch.sample_rate,clipping:view.peak>1,reference:ref?signalView(ref,patch.sample_rate):null,difference:ref?signalView(Float64Array.from(samples,(v,i)=>ref[i]-v),patch.sample_rate):null,errors:null};
  self.postMessage({id,phase:'analysis-ready',result,metrics:{analysis_ms:performance.now()-begun}});
 }catch(e){self.postMessage({id,phase:'error',error:e instanceof Error?e.message:'Rendu local impossible.'})}
};
