from pathlib import Path
import numpy as np
from scipy import optimize,signal
from time import monotonic
from lab.schema import Patch,Weights
from lab.graph import render
from lab.audio import read_wav,excerpt
from lab.metrics import Objective
from lab.attack_fit import calibrate_attack
root=Path(__file__).resolve().parents[2]
for stem in ('piano2','piano'):
 fs=48000;x=excerpt(read_wav((root.parent/f'{stem}.wav').read_bytes(),stem),0,3,fs);obj=Objective(x,fs,Weights())
 for count in (6,8,10):
  clock=monotonic();p=Patch.model_validate_json((root/'experiments/compact'/f'{stem}-{count}.monpatch').read_text());m=[n for n in p.nodes if n.type=='modal'];v=[n.parameters for n in m];onset=v[0]['onset'];attack=v[0]['attack']
  down=max(1,min(4,int(fs/(max(n['frequency'] for n in v)*2.5))))
  xx=signal.resample_poly(x,1,down);t=np.arange(len(xx))*down/fs;valid=t>=onset+.004;u=t[valid]-onset;xx=xx[valid]
  f=np.array([n['frequency'] for n in v]);amp=np.array([n['amplitude'] for n in v]);ph=np.array([n['phase'] for n in v]);tau=np.array([n['tau'] for n in v]);scale=max(np.linalg.norm(xx),1e-12);env=-np.expm1(-u[:,None]/attack)
  def evaluate(z,jac=False):
   a,b,df,lt=z.reshape(4,count);tt=np.exp(lt);ee=np.exp(-u[:,None]/tt)*env;angle=2*np.pi*u[:,None]*(f+df);ss=np.sin(angle);cc=np.cos(angle);yy=ee*(a*ss+b*cc)
   if jac:return np.column_stack([ee*ss,ee*cc,ee*(a*cc-b*ss)*2*np.pi*u[:,None],yy*u[:,None]/tt])/scale
   return (yy.sum(axis=1)-xx)/scale
  z0=np.r_[amp*np.cos(ph),amp*np.sin(ph),np.zeros(count),np.log(tau)]
  result=optimize.least_squares(evaluate,z0,jac=lambda z:evaluate(z,True),bounds=(np.r_[np.full(count*2,-4),np.full(count,-3),np.full(count,np.log(.015))],np.r_[np.full(count*2,4),np.full(count,3),np.full(count,np.log(30))]),max_nfev=65,ftol=1e-6,xtol=1e-6,gtol=1e-6,x_scale='jac')
  a,b,df,lt=result.x.reshape(4,count)
  for i,node in enumerate(m):node.parameters.update(amplitude=float(np.hypot(a[i],b[i])),phase=float(np.arctan2(b[i],a[i])),frequency=float(f[i]+df[i]),tau=float(np.exp(lt[i])))
  cal,diag=calibrate_attack(p,obj)
  if obj(render(cal))<obj(render(p)):p=cal
  print(stem,count,'joint',obj(render(p)),'time',monotonic()-clock,'nfev',result.nfev,flush=True)
  (root/'experiments/compact'/f'{stem}-{count}-joint.monpatch').write_text(p.model_dump_json(indent=2))
