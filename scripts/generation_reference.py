"""Synthetic native reference for validate_generation_wasm.mjs (no user audio)."""
import json
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
path=Path(__file__).resolve().parents[1]/'.local/generation-wasm-reference.json'
path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(reference,allow_nan=False))
