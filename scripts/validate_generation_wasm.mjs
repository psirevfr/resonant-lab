// Actual Python/WebAssembly under Node. No assertion about physical mobile devices.
// Tolerances declared before comparison: max/RMS 1e-7, objective 1e-8.
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {performance} from 'node:perf_hooks';
const root=resolve(import.meta.dirname,'..'),directory=resolve(root,'.local/compute-runtime');
const fixture=JSON.parse(await readFile(resolve(root,'.local/generation-wasm-reference.json'),'utf8'));
const {loadPyodide}=await import(pathToFileURL(resolve(directory,'pyodide.mjs')).href);
const begun=performance.now(),py=await loadPyodide({indexURL:directory+'/',stdout:()=>{},stderr:()=>{}});
await py.loadPackage(['numpy','scipy','pydantic']);
py.unpackArchive(Uint8Array.from(await readFile(resolve(directory,'numerical.zip'))),'zip',{extractDir:'/home/pyodide'});
py.runPython('import sys,json,numpy as np,scipy\nsys.path.insert(0,"/home/pyodide")\nfrom lab.compute import compute\nfrom lab.graph import render\nfrom lab.schema import Patch');
const initialization_ms=performance.now()-begun;
py.globals.set('fixture_json',JSON.stringify(fixture));
const start=performance.now();
const result=JSON.parse(py.runPython(`f=json.loads(fixture_json)
r=compute('generate',f['request'],np.array(f['input']),f['fs'])
y=render(Patch.model_validate(r['patch']))
e=y-np.array(f['output'])
comb=render(Patch.model_validate(f['comb_patch']))-np.array(f['comb_output'])
from lab.hybrid import high_band_candidates
from lab.metrics import Objective
from lab.schema import Weights
h=f['hybrid'];hp=Patch.model_validate(h['patch']);hx=np.array(h['input']);obj=Objective(hx,hp.sample_rate,Weights())
hq=min(high_band_candidates(hp,hx,obj,300),key=lambda q:obj(render(q)))
hy=render(hq);he=hy-np.array(h['output'])
json.dumps({'hybrid_max':float(np.max(abs(he))),'hybrid_objective_abs':abs(obj(hy)-h['error']),'hybrid_types':[n.type for n in hq.nodes],'wave_max':float(np.max(abs(e))),'wave_rms':float(np.sqrt(np.mean(e*e))),'comb_max':float(np.max(abs(comb))),'objective_abs':abs(r['candidates'][0]['errors']['total']-f['error']),'types':[n['type'] for n in r['patch']['nodes']],'comb_candidates':sum(any(n['type']=='comb' for n in c['patch']['nodes']) for c in r['candidates']),'algorithm_version':r['compute_metrics']['algorithm_version']})`));
result.compute_ms=performance.now()-start;
result.passed=result.wave_max<=1e-7&&result.wave_rms<=1e-7&&result.comb_max<=1e-7&&result.objective_abs<=1e-8&&result.comb_candidates===2&&result.hybrid_max<=1e-7&&result.hybrid_objective_abs<=1e-8&&JSON.stringify(result.hybrid_types)===JSON.stringify(fixture.hybrid.types)&&JSON.stringify(result.types)===JSON.stringify(fixture.types);
const report={environment:'Node + Pyodide, pas un navigateur ni un appareil mobile physique',initialization_ms,tolerances:{wave_max:1e-7,wave_rms:1e-7,comb_max:1e-7,objective_abs:1e-8},result,versions:JSON.parse(py.runPython('json.dumps({"python":sys.version.split()[0],"numpy":np.__version__,"scipy":scipy.__version__})'))};
await writeFile(resolve(root,process.argv[2]??'docs/generation-wasm-validation.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
if(!result.passed)process.exitCode=1;
