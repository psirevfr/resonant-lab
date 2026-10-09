// Actual Python/WebAssembly runtime, executed in Node; not a physical browser test.
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {performance} from 'node:perf_hooks';
const root=resolve(import.meta.dirname,'..'),directory=resolve(root,'.local/compute-runtime');
const reference=JSON.parse(await readFile(resolve(root,'.local/compute-reference.json'),'utf8'));
const {loadPyodide}=await import(pathToFileURL(resolve(directory,'pyodide.mjs')).href);
const begun=performance.now();
const py=await loadPyodide({indexURL:directory+'/',stdout:()=>{},stderr:()=>{}});
await py.loadPackage(['numpy','scipy','pydantic']);
py.unpackArchive(Uint8Array.from(await readFile(resolve(directory,'numerical.zip'))),'zip',{extractDir:'/home/pyodide'});
py.runPython('import sys\nsys.path.insert(0,"/home/pyodide")\nimport json,numpy as np,scipy\nfrom lab.compute import compute\nfrom lab.schema import Patch\nfrom lab.graph import render');
const initialization_ms=performance.now()-begun;
py.globals.set('reference_json',JSON.stringify(reference));
py.runPython('reference=json.loads(reference_json)\nx=np.array(reference["samples"],dtype=np.float64)');
// Tolerances chosen before comparison: full rendered waveform max/RMS <=1e-7;
// weighted objective absolute difference <=1e-8. Same architecture additionally required.
const report={measured_at:new Date().toISOString(),machine:reference.machine,repetitions:3,native_versions:reference.native_versions,source_sha256:JSON.parse(await readFile(resolve(directory,'manifest.json'),'utf8')).source_sha256,environment:'Node Python/WebAssembly (not browser)',node:process.version,initialization_ms,download_bytes:JSON.parse(await readFile(resolve(directory,'manifest.json'),'utf8')).download_bytes,tolerances:{wave_max:1e-7,wave_rms:1e-7,objective_abs:1e-8},operations:{}};
for(const kind of Object.keys(reference.requests)){
 py.globals.set('kind',kind);const runs=[],comparisons=[];let metrics;
 for(let i=0;i<3;i++){
  const start=performance.now();
  py.runPython("result=compute(kind,reference['requests'][kind],x,reference['sample_rate'])");
  runs.push(performance.now()-start);
  metrics=JSON.parse(py.runPython(`y=render(Patch.model_validate(result['patch']))
ref=reference['references'][kind]
error=y-np.array(ref['samples'])
value=result.get('final',result.get('candidates',[{}])[0].get('errors',{}).get('total',0))
refvalue=ref['result'].get('final',ref['result'].get('candidates',[{}])[0].get('errors',{}).get('total',0))
json.dumps({'wave_max':float(np.max(np.abs(error))),'wave_rms':float(np.sqrt(np.mean(error*error))),'objective_abs':abs(value-refvalue),'same_architecture':[(n['id'],n['type']) for n in result['patch']['nodes']]==[(n['id'],n['type']) for n in ref['result']['patch']['nodes']]})`));
  comparisons.push(metrics);
 }
 console.log('Completed:',kind);
 report.operations[kind]={native_ms:reference.native_ms[kind],wasm_ms:runs,comparisons,wave_max:Math.max(...comparisons.map(m=>m.wave_max)),wave_rms:Math.max(...comparisons.map(m=>m.wave_rms)),objective_abs:Math.max(...comparisons.map(m=>m.objective_abs)),same_architecture:comparisons.every(m=>m.same_architecture),passed:comparisons.every(m=>m.wave_max<=1e-7&&m.wave_rms<=1e-7&&m.objective_abs<=1e-8&&m.same_architecture)};
}
report.versions=JSON.parse(py.runPython('json.dumps({"python":sys.version.split()[0],"numpy":np.__version__,"scipy":scipy.__version__})'));
await writeFile(resolve(root,'docs/compute-benchmark.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
if(Object.values(report.operations).some(r=>!r.passed))process.exitCode=1;
