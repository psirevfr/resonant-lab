import json
from pathlib import Path
from time import perf_counter
from lab.schema import Patch,Weights
from lab.audio import read_wav,excerpt,wav_bytes
from lab.graph import render
from lab.metrics import Objective
from lab.nonlinear_fit import search
from lab.compact import tidy
root=Path(__file__).resolve().parents[2]
for stem in ('piano2','piano'):
 x=excerpt(read_wav((root.parent/f'{stem}.wav').read_bytes(),stem),0,3,48000);obj=Objective(x,48000,Weights());sources=[]
 for count in (2,4,6,8):
  path=root/'experiments/compact'/f'{stem}-{count}.monpatch'
  p=tidy(Patch.model_validate_json(path.read_text()));sources.append(p)
 t=perf_counter();patches,diagnostics=search(sources,x,Weights(),obj)
 for p,info in zip(patches,diagnostics):
  print(stem,info,flush=True)
  (root/'experiments/nonlinear'/f'{stem}-{info["sources"]}-{p.name.split(" · ")[1].split()[0]}.monpatch').write_text(p.model_dump_json(indent=2))
 (root/'experiments/nonlinear'/f'{stem}-results.json').write_text(json.dumps(diagnostics,indent=2))
 print('seconds',perf_counter()-t,flush=True)
