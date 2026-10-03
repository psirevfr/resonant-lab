import {renderGraph,signalView,encodeWav} from './audioDsp';
import type {Patch,Catalog} from './types';
self.onmessage=(event:MessageEvent<{patch:Patch;catalog:Catalog;reference?:Float64Array}>)=>{
 try{const {patch,catalog,reference}=event.data,samples=renderGraph(patch,catalog),wav=encodeWav(samples,patch.sample_rate),view=signalView(samples,patch.sample_rate);
 const ref=reference&&reference.length===samples.length?reference:undefined;
 const result={id:'local',view,sample_rate:patch.sample_rate,clipping:view.peak>1,reference:ref?signalView(ref,patch.sample_rate):null,difference:ref?signalView(Float64Array.from(samples,(v,i)=>ref[i]-v),patch.sample_rate):null,errors:null};
 self.postMessage({wav,result},{transfer:[wav]});
 }catch(e){self.postMessage({error:e instanceof Error?e.message:'Rendu local impossible.'})}
};
