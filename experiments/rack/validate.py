import json,time
from pathlib import Path
from lab.schema import Patch,Weights
from lab.audio import read_wav,excerpt,wav_bytes
from lab.compact import simplify
from lab.instrument import expand_modes
from lab.graph import render
root=Path(__file__).resolve().parents[2]
results=[]
for name in ('piano2','piano'):
 p=Patch.model_validate_json((root/f'examples/{name}-impact.monpatch').read_text())
 rec=read_wav((root.parent/f'{name}.wav').read_bytes(),name)
 x=excerpt(rec,0,p.duration,p.sample_rate)
 start=time.monotonic();r=simplify(p,x,Weights(),protect_texture=True)
 q=expand_modes(Patch.model_validate(r['patch']))
 (root/f'examples/{name}-rack.monpatch').write_text(q.model_dump_json(indent=2))
 (root/f'examples/{name}-rack.wav').write_bytes(wav_bytes(render(q),q.sample_rate))
 summary={k:v for k,v in r.items() if k not in ('patch','original','candidates')}
 summary.update(name=name,seconds=time.monotonic()-start,candidates=[{k:v for k,v in c.items() if k!='patch'}|{'name':c['patch']['name']} for c in r['candidates']])
 results.append(summary)
 (root/'docs/rack-validation.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
 print(name,r['original_blocks'],r['final_blocks'],r['baseline'],r['final'],q.name,flush=True)
