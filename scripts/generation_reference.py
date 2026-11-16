"""Synthetic native reference for validate_generation_wasm.mjs (no user audio)."""
import json,runpy,sys
from pathlib import Path
import numpy as np
from lab.compute import compute
from lab.graph import render
from lab.schema import Patch,Block
from lab.identify import link
fs=44100;t=np.arange(6615)/fs
x=(1-np.exp(-t/.003))*np.exp(-t/.3)*(.3*np.sin(2*np.pi*300*t)+.08*np.sin(2*np.pi*600*t))
request={'audio_id':'synthetic','duration':len(x)/fs,'max_partials':4,'refine_modes':False,'include_impact':False,'detailed':False}
r=compute('generate',request,x,fs)
p=Patch.model_validate(r['patch'])
comb=Patch(duration=.15,nodes=[Block(id='osc',type='oscillator',parameters={'frequency':731,'amplitude':.31,'phase':.2}),Block(id='comb',type='comb',parameters={'frequency':261.63,'feedback':.9999}),Block(id='out',type='output')],edges=[link('osc','comb'),link('comb','out')])
reference={'request':request,'input':x.tolist(),'fs':fs,'output':render(p).tolist(),'error':r['candidates'][0]['errors']['total'],'types':[n.type for n in p.nodes],'comb_patch':comb.model_dump(),'comb_output':render(comb).tolist()}
root=Path(__file__).resolve().parents[1]
from lab.hybrid import high_band_candidates
from lab.metrics import Objective
from lab.schema import Weights
hp,hx=runpy.run_path(str(root/'backend/tests/test_hybrid.py'))['fixture']()
objective=Objective(hx,hp.sample_rate,Weights())
hq=min(high_band_candidates(hp,hx,objective,300),key=lambda q:objective(render(q)))
reference['hybrid']={'patch':hp.model_dump(),'input':hx.tolist(),'output':render(hq).tolist(),'types':[n.type for n in hq.nodes],'error':objective(render(hq))}
from lab.harmonic_groups import harmonic_candidates
sys.path.insert(0,str(root/'backend/tests'))
from test_harmonic_groups import fixture as harmonic_fixture
ap,ax=harmonic_fixture();ao=Objective(ax,ap.sample_rate,Weights())
aq=min(harmonic_candidates(ap,ax,Weights()),key=lambda q:ao(render(q)))
reference['harmonic']={'patch':ap.model_dump(),'input':ax.tolist(),'output':render(aq).tolist(),'types':[n.type for n in aq.nodes],'error':ao(render(aq))}
path=root/'.local/generation-wasm-reference.json'
path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(reference,allow_nan=False))
