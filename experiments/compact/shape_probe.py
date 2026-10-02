from pathlib import Path
import numpy as np
from scipy import optimize
from lab.schema import Patch, Weights
from lab.graph import render
from lab.audio import read_wav,excerpt
from lab.blocks import process
from lab.metrics import Objective
from lab.impact import fit_impact
root=Path(__file__).resolve().parents[2]
for stem in ('piano2','piano'):
 rec=read_wav((root.parent/f'{stem}.wav').read_bytes(),stem);fs=rec.sample_rate;x=excerpt(rec,0,3,fs);obj=Objective(x,fs,Weights())
 for count in (4,6,8,10):
  p=Patch.model_validate_json((root/'experiments/compact'/f'{stem}-{count}.monpatch').read_text());y=render(p)
  best=[obj(y),y,None]
  # Existing blocks only: mild-to-strong tanh, LP and gain, globally evaluated.
  def shape(v):
   z=np.tanh(v[0]*y)
   z=process('lowpass',{'fc':np.exp(v[1]),'q':v[2]},[z],fs,len(z))
   return v[3]*z
  def cost(v):
   z=shape(v);e=obj(z)
   if e<best[0]:best[:]=[e,z,v.copy()]
   return e
  r=optimize.minimize(cost,[1,np.log(fs*.45),.707,1],method='Powell',bounds=[(.1,20),(np.log(500),np.log(fs*.49)),(.5,2),(.02,4)],options={'maxfev':160,'maxiter':4})
  imp=fit_impact(p,x,{'onset':p.nodes[0].parameters['onset']},obj)
  ie=obj(render(imp)) if imp else obj(y)
  if imp:(root/'experiments/compact'/f'{stem}-{count}-impact.monpatch').write_text(imp.model_dump_json(indent=2))
  print(stem,count,'plain',obj(y),'shaped',best[0],'shape',None if best[2] is None else best[2].tolist(),'impact',ie,flush=True)
