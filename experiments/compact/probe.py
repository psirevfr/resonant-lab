from pathlib import Path
import json
import numpy as np
from scipy import optimize
from lab.schema import Patch, Weights
from lab.graph import render
from lab.audio import read_wav,excerpt
from lab.blocks import process
from lab.identify import modal_patch
from lab.metrics import Objective
root=Path(__file__).resolve().parents[2]
for stem in ('piano2','piano'):
 p=Patch.model_validate_json((root/'examples'/f'{stem}-impact.monpatch').read_text())
 fs=p.sample_rate;x=excerpt(read_wav((root.parent/f'{stem}.wav').read_bytes(),stem),0,p.duration,fs); obj=Objective(x,fs,Weights())
 modes=[n for n in p.nodes if n.type=='modal'];t=np.arange(len(x))/fs
 columns=[]
 for node in modes:
  v=node.parameters;u=np.maximum(0,t-v['onset']);e=np.exp(-u/v['tau'])*(-np.expm1(-u/v['attack']))*(t>=v['onset'])
  columns.extend([e*np.sin(2*np.pi*v['frequency']*u),e*np.cos(2*np.pi*v['frequency']*u)])
 D=np.array(columns).T;G=D.T@D;b=D.T@x;chosen=[];res=x.copy();rows=[]
 for count in range(1,min(16,len(modes))+1):
  candidates=[]
  for j in range(len(modes)):
   if j in chosen:continue
   ids=[k for m in chosen+[j] for k in (2*m,2*m+1)]
   co=np.linalg.lstsq(G[np.ix_(ids,ids)],b[ids],rcond=1e-9)[0]
   improvement=2*co@b[ids]-co@G[np.ix_(ids,ids)]@co
   candidates.append((improvement,j,co,ids))
  _,j,co,ids=max(candidates,key=lambda v:v[0]);chosen.append(j)
  if count not in (2,4,6,8,10,12,16):continue
  partials=[]
  for k,m in enumerate(chosen):
   v=modes[m].parameters
   partials.append({**v,'amplitude':float(np.hypot(co[2*k],co[2*k+1])),'phase':float(np.arctan2(co[2*k+1],co[2*k])),'decay_r2':None})
  q=modal_patch({'partials':partials,'onset':modes[0].parameters['onset'],'attack':modes[0].parameters['attack']},fs,p.duration,count)
  y=render(q);err=obj.components(y);rows.append({'modes':count,'error':err['total'],'time':err['time']})
  (root/'experiments/compact'/f'{stem}-{count}.monpatch').write_text(q.model_dump_json(indent=2))
 print(stem,'baseline',obj(render(p)),rows,flush=True)
