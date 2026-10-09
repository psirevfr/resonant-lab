#!/usr/bin/env python3
"""Reproducible synthetic shared-algorithm reference; never accesses a user database."""
import json,time,platform
from pathlib import Path
import numpy as np,scipy
from lab.compute import compute
from lab.graph import render
from lab.schema import Patch,Block,Edge

fs=44100;duration=.15;t=np.arange(round(fs*duration))/fs
x=sum(a*np.exp(-t/tau)*(-np.expm1(-t/.003))*np.sin(2*np.pi*f*t) for a,f,tau in [(.3,440,.4),(.12,880,.2),(.05,1320,.12)])
p=Patch(duration=duration,nodes=[Block(id=f'm{i}',type='modal',parameters={'frequency':f,'amplitude':a,'tau':tau,'attack':.003,'onset':0,'phase':0}) for i,(a,f,tau) in enumerate([(.25,440,.4),(.1,880,.2),(.04,1320,.12)])]+[Block(id='sum',type='sum'),Block(id='out',type='output')],edges=[Edge(id=f'e{i}',source=f'm{i}',target='sum') for i in range(3)]+[Edge(id='out',source='sum',target='out')])
requests={
 'generate':{'audio_id':'synthetic','duration':duration,'max_partials':3,'detailed':True,'refine_modes':True,'include_impact':True},
 'optimize':{'audio_id':'synthetic','patch':p.model_dump(),'max_iterations':3,'parameter_ids':['m0:amplitude'],'method':'Powell'},
 'compact':{'audio_id':'synthetic','patch':p.model_dump(),'test_shaping':True,'protect_texture':True,'tolerance':.2},
}
results={};timings={}
for kind,request in requests.items():
 runs=[]
 for repeat in range(3):
  start=time.perf_counter();result=compute(kind,request,x,fs);runs.append((time.perf_counter()-start)*1000)
 results[kind]={'result':result,'samples':render(Patch.model_validate(result['patch'])).tolist()};timings[kind]=runs
out=Path('.local/compute-reference.json');out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({'sample_rate':fs,'samples':x.tolist(),'requests':requests,'references':results,'native_ms':timings,'native_versions':{'numpy':np.__version__,'scipy':scipy.__version__},'machine':platform.platform(),'repetitions':3},allow_nan=False))
print(json.dumps({'native_ms':timings,'reference':str(out)}))
