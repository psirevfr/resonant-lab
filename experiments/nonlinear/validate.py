from pathlib import Path
from time import perf_counter
import json
import numpy as np
from lab.compact import simplify
from lab.schema import Patch,Weights
from lab.graph import render
from lab.audio import read_wav,excerpt,wav_bytes
root=Path(__file__).resolve().parents[2]
results=[]
def timing(p):
 render(p)
 times=[]
 for _ in range(9):
  t=perf_counter();render(p);times.append(perf_counter()-t)
 return float(np.median(times)*1000)
for stem in ('piano2','piano'):
 p=Patch.model_validate_json((root/'examples'/f'{stem}-impact.monpatch').read_text())
 x=excerpt(read_wav((root.parent/f'{stem}.wav').read_bytes(),stem),0,p.duration,p.sample_rate)
 t=perf_counter();r=simplify(p,x,Weights());elapsed=perf_counter()-t
 q=Patch.model_validate(r['patch'])
 (root/'examples'/f'{stem}-global.monpatch').write_text(q.model_dump_json(indent=2))
 (root/'examples'/f'{stem}-global.wav').write_bytes(wav_bytes(render(q),q.sample_rate))
 summary={k:v for k,v in r.items() if k not in ('patch','original','candidates')}
 summary.update(file=stem,seconds=elapsed,original_render_ms=timing(p),compact_render_ms=timing(q),candidates=[{**{k:v for k,v in c.items() if k!='patch'},'name':c['patch']['name'],'blocks':len(c['patch']['nodes'])} for c in r['candidates']])
 results.append(summary)
 print(json.dumps({k:v for k,v in summary.items() if k not in ('candidates','utilities')},ensure_ascii=False),flush=True)
 (root/'docs/global-processing-validation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
