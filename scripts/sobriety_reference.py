"""Synthetic native fixtures for validate_sobriety_wasm.mjs; needs test dependencies."""
import json,runpy
from pathlib import Path
from lab.compute import compute
from lab.graph import render
from lab.schema import Patch
root=Path(__file__).resolve().parents[1]
fixtures=runpy.run_path(str(root/'backend/tests/test_sobriety.py'))
p,x=fixtures['nonlinear_fixture']()
reference={}
for name in ('nonlinear-bank','reloaded-shared'):
    request={'audio_id':'synthetic','patch':p.model_dump(),'tolerance':.2,'test_shaping':name=='nonlinear-bank','test_noise':False,'protect_texture':True}
    r=compute('compact',request,x,p.sample_rate)
    q=Patch.model_validate(r['patch'])
    reference[name]={'request':request,'input':x.tolist(),'fs':p.sample_rate,'output':render(q).tolist(),'error':r['final'],'types':[n.type for n in q.nodes]}
    p=q;x=render(q)
(root/'.local/sobriety-wasm-reference.json').write_text(json.dumps(reference,allow_nan=False))
