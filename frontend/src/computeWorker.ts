/// <reference lib="webworker" />
const scope=self as unknown as DedicatedWorkerGlobalScope;
let runtime:Promise<any>|null=null;
async function initialize(id:string){
 const begun=performance.now();scope.postMessage({id,phase:'initializing'});
 const base=new URL('/compute-runtime/',scope.location.origin).href;
 const manifest=await fetch(base+'manifest.json').then(r=>{if(!r.ok)throw Error('Runtime indisponible');return r.json()});
 if(!manifest.ready||manifest.runtime_version!=='314.0.7')throw Error('Runtime incompatible');
 const {loadPyodide}=await import(/* @vite-ignore */ base+'pyodide.mjs');
 const py=await loadPyodide({indexURL:base,stdout:()=>{},stderr:()=>{}});
 await py.loadPackage(['numpy','scipy','pydantic']);
 const archive=await fetch(base+'numerical.zip').then(r=>{if(!r.ok)throw Error('Sources indisponibles');return r.arrayBuffer()});
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',archive)),b=>b.toString(16).padStart(2,'0')).join('');
 if(digest!==manifest.source_sha256)throw Error('Sources incompatibles');
 py.unpackArchive(new Uint8Array(archive),'zip',{extractDir:'/home/pyodide'});
 await py.runPythonAsync('import sys\nsys.path.insert(0,"/home/pyodide")\nfrom lab.compute import compute\nimport json,numpy as np');
 return {py,manifest,initialization_ms:performance.now()-begun};
}
scope.onmessage=async event=>{
 const {id,kind,request,samples,sampleRate}=event.data;
 try{
  const cold=!runtime;runtime??=initialize(id);
  const {py,manifest,initialization_ms}=await runtime;
  scope.postMessage({id,phase:'computing'});
  py.globals.set('__kind',kind);py.globals.set('__request',JSON.stringify(request));py.globals.set('__samples',samples);py.globals.set('__fs',sampleRate);
  py.globals.set('__progress',(value:string)=>scope.postMessage({id,phase:'progress',progress:JSON.parse(value)}));
  const begun=performance.now();
  try{
   const result=JSON.parse(await py.runPythonAsync('json.dumps(compute(__kind,json.loads(__request),np.asarray(__samples.to_py(),dtype=np.float64),__fs,lambda value: __progress(json.dumps(value))),allow_nan=False)'));
   scope.postMessage({id,phase:'result',result,metrics:{worker_compute_ms:performance.now()-begun,initialization_ms:cold?initialization_ms:0,source_sha256:manifest.source_sha256,runtime_version:manifest.runtime_version}});
  }finally{for(const key of ['__kind','__request','__samples','__fs','__progress'])py.globals.delete(key)}
 }catch{scope.postMessage({id,phase:'error',error:'Calcul local indisponible ou entrée incompatible. Vous pouvez relancer explicitement sur le serveur.'})}
};
export {};
